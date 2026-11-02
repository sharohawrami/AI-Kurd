"""Kurdistan AI Safety Hub: the website with its admin panel.

Run locally:   python app.py            (then open http://localhost:8000)
Production:    gunicorn -w 2 -b 0.0.0.0:8000 app:app

Settings come from environment variables (see README.md); data lives in KAISH_DATA_DIR
(default ./instance): the SQLite database, uploaded pictures and the session secret.
"""
import collections
import csv
import datetime
import functools
import html as H
import io
import json
import os
import pathlib
import re
import secrets
import smtplib
import threading
import time
import unicodedata
from email.message import EmailMessage

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import db as dbm
import renderer as R

ROOT = pathlib.Path(__file__).resolve().parent
FORMS = ("cohort", "interest", "staff", "newsletter")
LANGS = ("en", "ku")
LANG_NAMES = {"en": "English", "ku": "Kurdish (Sorani)"}
MIN_PASSWORD = 10
ADMIN_SESSION_HOURS = 12


# ---------------------------------------------------------------- app setup
def load_secret():
    env = os.environ.get("KAISH_SECRET_KEY")
    if env:
        return env
    dbm.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = dbm.DATA_DIR / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text().strip()


app = Flask(__name__, static_folder=None, template_folder=str(ROOT / "templates"))
app.config.update(
    SECRET_KEY=load_secret(),
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,
    MAX_FORM_MEMORY_SIZE=4 * 1024 * 1024,
    MAX_FORM_PARTS=5000,
    SESSION_COOKIE_NAME="kaish_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("KAISH_SECURE_COOKIES", "0") == "1",
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30),  # members; admin sign-ins expire after 12 hours
)
if os.environ.get("KAISH_PROXY", "0") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

with dbm.connect() as _con:
    dbm.init(_con)


def get_db():
    if "db" not in g:
        g.db = dbm.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    con = g.pop("db", None)
    if con is not None:
        con.close()


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if request.path.startswith(("/admin", "/login")):
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Frame-Options"] = "DENY"
    return resp


# ---------------------------------------------------------------- users and sessions
def current_user():
    if "user" in g:
        return g.user
    g.user = None
    uid, tok = session.get("uid"), session.get("tok")
    if uid and tok:
        fresh = time.time() - session.get("uat", 0) < ADMIN_SESSION_HOURS * 3600
        row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone() if fresh else None
        if row and row["active"] and secrets.compare_digest(row["session_token"], tok):
            g.user = row
    return g.user


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def check_csrf():
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
    if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
        abort(400, "This form has expired. Go back, reload the page and try again.")


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login", next=request.full_path if request.method == "GET" else None))
        if request.method == "POST":
            check_csrf()
        if user["must_change_password"] and request.endpoint not in ("account", "logout"):
            flash("Choose a new password before you continue.", "warn")
            return redirect(url_for("account"))
        if user["role"] == "university" and request.endpoint not in UNI_ENDPOINTS:
            if request.method == "GET":
                return redirect(url_for("uni_home"))
            abort(403, "University accounts can only manage their own university.")
        return view(*args, **kwargs)
    return wrapper


UNI_ENDPOINTS = {"uni_home", "uni_edit", "news_list", "news_edit", "news_delete", "uni_courses", "course_edit",
                 "course_delete", "course_applications", "course_application", "course_application_delete",
                 "course_applications_csv", "account", "logout", "dashboard"}


def is_staff(user):
    return bool(user) and user["role"] in ("superadmin", "admin")


def superadmin_required(view):
    @functools.wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user()["role"] != "superadmin":
            abort(403, "Only a superadmin can manage admin accounts.")
        return view(*args, **kwargs)
    return wrapper


def log(action, detail=""):
    user = current_user()
    dbm.log(get_db(), user["id"] if user else None, action, detail)


@app.context_processor
def template_globals():
    return {"csrf_token": csrf_token, "me": current_user(), "lang_names": LANG_NAMES, "is_staff": is_staff}


def password_problem(pw, username=""):
    if len(pw) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if username and username.lower() in pw.lower():
        return "Don't include your username in your password."
    if len(set(pw)) < 5:
        return "Use a less repetitive password."
    return None


temp_password = dbm.temp_password
DUMMY_HASH = generate_password_hash(secrets.token_hex(16))


# ---------------------------------------------------------------- rendering public pages
def site_values(con):
    """site.json values with every change saved in the admin panel on top."""
    values = dict(R.load_site()["values"])
    values.update(dbm.settings(con))
    return values


def make_renderer(edit=False, collect=False, posts=None):
    con = get_db()
    r = R.Renderer(values=site_values(con), texts=dbm.text_overrides(con),
                   posts=dbm.published_posts(con) if posts is None else posts,
                   endpoint="/api/submit", edit=edit, collect=collect, accounts=True, hidden=dbm.hidden(con))
    member = None if collect else current_member()
    if member:
        r.set_member(member, avatar_html(member))
    return r


def page_catalog():
    """{(lang, name): {"out", "url", "meta"}} for every page, including the news article template."""
    cat = {}
    for lang, name, meta, _body in R.page_sources():
        out = R.out_path(lang, meta)
        url = "/" + (out[: -len("index.html")] if out.endswith("index.html") else out[:-5])
        cat[(lang, name)] = {"out": out, "url": url, "meta": meta}
    return cat


CATALOG = page_catalog()
ROUTES = {}
for (_lang, _name), _info in CATALOG.items():
    if _name == "news-post" or _info["meta"].get("dynamic"):
        continue
    _out = _info["out"]
    ROUTES[_out] = (_lang, _name)
    ROUTES[_out[:-5]] = (_lang, _name)
    if _out.endswith("index.html"):
        ROUTES[_out[: -len("index.html")]] = (_lang, _name)
POST_ROUTE = re.compile(r"^(ku/)?news/([a-z0-9][a-z0-9-]{0,80})(?:\.html)?$")


def admin_bar(user, lang, page, edit, editable=True):
    if not user:
        return "", ""
    if not is_staff(user):
        who = R.html.escape(user["display_name"])
        return ('<link rel="stylesheet" href="/assets/edit.css">',
                f'<div class="kab" role="region" aria-label="Account tools" data-edit="0"><span class="kab-who">{who}</span>'
                f'<a class="kab-btn" href="/admin/uni">University panel</a></div>')
    page_off = ""
    if ("page", "universities" if page in ("university", "course") else page) in dbm.hidden(get_db()):
        page_off = '<a class="kab-off" href="/admin/visibility">This page is hidden from visitors</a>'
    here = request.path
    texts_link = f"/admin/pages/{lang}/{page}"
    who = R.html.escape(user["display_name"])
    if edit:
        controls = (f'<span class="kab-state" data-count>No unsaved changes</span>'
                    f'<button type="button" class="kab-btn kab-save" data-save disabled>Save changes</button>'
                    f'<a class="kab-link" href="{here}" data-done>Finish editing</a>'
                    f'<a class="kab-link" href="{texts_link}">Hidden texts on this page</a>')
    elif editable:
        controls = (f'<a class="kab-btn" href="{here}?edit=1">Edit this page</a>'
                    f'<a class="kab-link" href="{texts_link}">All texts on this page</a>')
    else:
        controls = f'<a class="kab-btn" href="{texts_link}">Edit the texts on this page</a>'
    body = (f'<div class="kab" role="region" aria-label="Admin tools" data-csrf="{csrf_token()}" '
            f'data-lang="{lang}" data-page="{page}" data-edit="{1 if edit else 0}">'
            f'<span class="kab-who">{who}</span>{page_off}{controls}'
            f'<a class="kab-link" href="/admin">Admin panel</a></div>'
            f'<script src="/assets/edit.js" defer></script>')
    return '<link rel="stylesheet" href="/assets/edit.css">', body


def html_response(text, private=False):
    resp = Response(text, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store" if private else "no-cache"
    return resp


@app.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(ROOT / "assets", filename, max_age=3600)


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(ROOT / "assets", "favicon.ico", max_age=86400, mimetype="image/x-icon")


@app.get("/uploads/<path:filename>")
def uploads(filename):
    if not re.fullmatch(r"[a-f0-9]{24}\.(webp|jpg|png)", filename):
        abort(404)
    return send_from_directory(dbm.UPLOADS, filename, max_age=86400)


@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def public_page(path):
    if path == "ku":
        return redirect("/ku/", 301)
    user = current_user()
    edit = bool(is_staff(user) and request.args.get("edit") == "1" and not user["must_change_password"])
    m = POST_ROUTE.match(path)
    if m:
        lang = "ku" if m.group(1) else "en"
        post = get_db().execute("SELECT * FROM posts WHERE slug = ?", (m.group(2),)).fetchone()
        if not post or (not post["published"] and not (is_staff(user) or (user and post["university_id"]
                                                                                    and user["university_id"] == post["university_id"]))):
            abort(404)
        if post["university_id"]:
            uni = get_db().execute("SELECT * FROM universities WHERE id = ?", (post["university_id"],)).fetchone()
            if not uni or (not uni["published"] and not is_staff(user)) or (("page", "universities") in dbm.hidden(get_db()) and not is_staff(user)):
                abort(404)
        head, body = admin_bar(user, lang, "news-post", edit)
        post_d = dict(post)
        if post["university_id"]:
            post_d["_source"] = (uni_name(uni, lang), f"{R.UI[lang]['base']}universities/{uni['slug']}")
        page = make_renderer(edit=edit).render_post(lang, post_d, extra_head=head, extra_body=body,
                                                     draft=not post["published"])
        return html_response(page, private=bool(user or current_member()))
    if path not in ROUTES:
        abort(404)
    lang, name = ROUTES[path]
    if not is_staff(user) and ("page", name) in dbm.hidden(get_db()):
        abort(404)
    head, body = admin_bar(user, lang, name, edit)
    return html_response(make_renderer(edit=edit).render(lang, name, extra_head=head, extra_body=body),
                         private=bool(user or current_member()))


# ---------------------------------------------------------------- search engines
def site_base():
    """https://kaish.academy (from Dates and details), or the address this request came in on."""
    domain = (site_values(get_db()).get("domain") or "").strip().rstrip("/")
    return domain or request.url_root.rstrip("/")


@app.get("/robots.txt")
def robots_txt():
    body = ("User-agent: *\nDisallow: /admin\nDisallow: /login\nDisallow: /api/\nDisallow: /members/\n\n"
            f"Sitemap: {site_base()}/sitemap.xml\n")
    return Response(body, mimetype="text/plain", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/sitemap.xml")
def sitemap_xml():
    """Every public page in both languages, with each page's other-language version, for Google Search Console."""
    con, base = get_db(), site_base()
    hidden = dbm.hidden(con)
    loc = lambda out: base + "/" + (out[: -len("index.html")] if out.endswith("index.html") else out)
    pairs = []   # (english path, kurdish path, last changed)
    for (lang, name), info in CATALOG.items():
        if lang != "en" or name == "news-post" or info["meta"].get("dynamic") or ("page", name) in hidden:
            continue
        pairs.append((info["out"], CATALOG[("ku", name)]["out"], ""))
    unis_on = ("page", "universities") not in hidden
    live_unis = {u["id"]: u for u in con.execute("SELECT * FROM universities WHERE published = 1")} if unis_on else {}
    for p in con.execute("SELECT * FROM posts WHERE published = 1"):
        if p["university_id"] is None or p["university_id"] in live_unis:
            pairs.append((f"news/{p['slug']}.html", f"ku/news/{p['slug']}.html", (p["updated_at"] or "")[:10]))
    if unis_on:
        pairs.append(("universities.html", "ku/universities.html", ""))
        for u in live_unis.values():
            pairs.append((f"universities/{u['slug']}.html", f"ku/universities/{u['slug']}.html", (u["updated_at"] or "")[:10]))
        for c in con.execute("SELECT * FROM courses WHERE published = 1"):
            u = live_unis.get(c["university_id"])
            if u:
                path = f"universities/{u['slug']}/courses/{c['slug']}.html"
                pairs.append((path, "ku/" + path, (c["updated_at"] or "")[:10]))
    rows = []
    for en, ku, changed in pairs:
        alts = (f'<xhtml:link rel="alternate" hreflang="en" href="{H.escape(loc(en))}"/>'
                f'<xhtml:link rel="alternate" hreflang="ckb" href="{H.escape(loc(ku))}"/>')
        mod = f"<lastmod>{changed}</lastmod>" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", changed) else ""
        for path in (en, ku):
            rows.append(f"<url><loc>{H.escape(loc(path))}</loc>{mod}{alts}</url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
           + "\n".join(rows) + "\n</urlset>\n")
    return Response(xml, mimetype="application/xml", headers={"Cache-Control": "public, max-age=3600"})


@app.errorhandler(404)
def not_found(_e):
    return render_template("admin/message.html", title="Page not found",
                           text="We couldn't find that page.", link="/", link_text="Go to the homepage"), 404


@app.errorhandler(403)
@app.errorhandler(400)
def refused(e):
    return render_template("admin/message.html", title="That didn't work", text=e.description,
                           link=request.referrer or "/admin", link_text="Go back"), e.code


@app.errorhandler(413)
def too_large(_e):
    return render_template("admin/message.html", title="File too large",
                           text="Pictures must be smaller than 10 MB.", link=request.referrer or "/admin",
                           link_text="Go back"), 413


# ---------------------------------------------------------------- public form submissions
_RATE = collections.defaultdict(collections.deque)


def rate_limited(key, limit=30, window=3600):
    q, t = _RATE[key], time.time()
    while q and q[0] < t - window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(t)
    return False


@app.post("/api/submit")
def api_submit():
    if rate_limited(request.remote_addr or "?"):
        return jsonify(ok=False, error="Too many submissions from this connection. Try again later."), 429
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("fields"), dict):
        return jsonify(ok=False, error="Invalid submission."), 400
    course = None
    cm = re.fullmatch(r"course:(\d{1,9})", str(data.get("form", "")))
    if cm:
        course = open_course(get_db(), int(cm.group(1)))
        if not course:
            return jsonify(ok=False, error="This course isn't taking applications."), 400
    elif data.get("form") not in FORMS:
        return jsonify(ok=False, error="Invalid submission."), 400
    elif data["form"] == "cohort" and not applications_open():
        return jsonify(ok=False, error="Applications for Cohort 1 are closed."), 400
    if data.get("website"):
        return jsonify(ok=True)
    fields = {}
    for k, v in list(data["fields"].items())[:80]:
        if isinstance(k, str) and re.fullmatch(r"[a-z0-9_]{1,60}", k):
            fields[k] = str(v)[:10000]
    if data["form"] != "newsletter" and not (fields.get("full_name") and fields.get("email")):
        return jsonify(ok=False, error="Name and email are required."), 400
    if course:
        questions = course_questions(course)
        allowed = {"full_name", "email", "phone", "consent_data", "language"} | {q["id"] for q in questions}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if any(q.get("required") and not fields.get(q["id"], "").strip() for q in questions) or not fields.get("consent_data"):
            return jsonify(ok=False, error="Answer every required question."), 400
    con = get_db()
    con.execute("INSERT INTO submissions (form, language, name, email, data, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (data["form"], fields.get("language", ""), fields.get("full_name", ""), fields.get("email", ""),
                 json.dumps(fields, ensure_ascii=False), dbm.now()))
    con.commit()
    if data["form"] in ("cohort", "staff", "interest") and email_enabled():
        values = site_values(con)
        threading.Thread(target=send_confirmations, args=(data["form"], fields, values), daemon=True).start()
    return jsonify(ok=True)


# ---------------------------------------------------------------- email (optional)
SMTP = {k: os.environ.get(f"KAISH_SMTP_{k.upper()}", "") for k in ("host", "port", "user", "password", "from")}
NOTIFY_EMAIL = os.environ.get("KAISH_NOTIFY_EMAIL", "")


def email_enabled():
    return bool(SMTP["host"] and SMTP["from"])


def send_mail(to, subject, body, reply_to=None):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = SMTP["from"], to, subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    port = int(SMTP["port"] or 587)
    cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with cls(SMTP["host"], port, timeout=20) as s:
        if port != 465:
            s.starttls()
        if SMTP["user"]:
            s.login(SMTP["user"], SMTP["password"])
        s.send_message(msg)


def send_confirmations(form, f, values):
    kurdish = f.get("language", "").startswith("Kurdish")
    v = lambda k: (values.get(k + "_ku") if kurdish and values.get(k + "_ku") else values.get(k)) or "[date]"
    first = (f.get("full_name", "").split() or ["هاوڕێ" if kurdish else "there"])[0]
    hub_ku = "ناوەندی کوردستان بۆ سەلامەتیی زیرەکیی دەستکرد"
    if form == "interest":
        if kurdish:
            subject = f"ناوت تۆمار کرا: خولی داهاتووی {v('program_name')}"
            body = (f"سڵاو {first}،\n\nسوپاس. هەر کە وەرگرتنی داواکاری بۆ خولی داهاتووی {v('program_name')} کرایەوە ئیمەیڵت بۆ دەنێرین.\n\n"
                    f"ئەگەر دەتەوێت ناوت لە لیستەکە لابەین، وەڵامی ئەم ئیمەیڵە بدەرەوە.\n\nتیمی {hub_ku} (KAISH)")
        else:
            subject = f"You're on the list for the next cohort of the {v('program_name')}"
            body = (f"Hi {first},\n\nThank you. We'll email you as soon as applications open for the next cohort of the {v('program_name')}.\n\n"
                    "To be removed from the list, reply to this email.\n\nThe Kurdistan AI Safety Hub team (KAISH)")
    elif kurdish and form == "cohort":
        subject = f"داواکارییەکەت گەیشت: {v('program_name')}، خولی یەکەم"
        body = (f"سڵاو {first}،\n\nسوپاس بۆ پێشکەشکردنی داواکاری بۆ خولی یەکەمی {v('program_name')}. هەنگاوەکانی داهاتوو ئەمانەن:\n\n"
                f"١. گفتوگۆ لەگەڵ ڕێکخەرانی دانیشتن لە نێوان {v('interviews_from')} و {v('interviews_to')} دەبێت.\n"
                f"٢. هەموو داواکاران تا {v('decisions_date')} بڕیارەکە وەردەگرن.\n\n"
                f"ئەگەر هەر شتێک لە داواکارییەکەتدا گۆڕا، وەڵامی ئەم ئیمەیڵە بدەرەوە.\n\nتیمی {hub_ku} (KAISH)")
    elif kurdish:
        subject = f"داواکارییەکەت بۆ بەشداربوون لە تیمی {hub_ku}"
        body = (f"سڵاو {first}،\n\nسوپاس بۆ داواکارییەکەت بۆ بەشداربوون لە تیمی ناوەندەکەمان. خۆمان هەموو داواکارییەک دەخوێنینەوە "
                f"و لە ماوەی {v('reply_days')} ڕۆژدا وەڵامت دەدەینەوە.\n\nتیمی {hub_ku} (KAISH)")
    elif form == "cohort":
        subject = f"We've received your application: {v('program_name')}, Cohort 1"
        body = (f"Hi {first},\n\nThank you for applying to Cohort 1 of the {v('program_name')}. Here's what happens next:\n\n"
                f"1. Conversations with facilitators take place between {v('interviews_from')} and {v('interviews_to')}.\n"
                f"2. Every applicant receives a decision by {v('decisions_date')}.\n\n"
                "If anything in your application changes, reply to this email.\n\nThe Kurdistan AI Safety Hub team (KAISH)")
    else:
        subject = "Your application to join the Kurdistan AI Safety Hub team"
        body = (f"Hi {first},\n\nThank you for applying to join the Kurdistan AI Safety Hub as {f.get('roles', 'a team member')}. "
                f"We read every application ourselves and will reply within {v('reply_days')} days.\n\n"
                "The Kurdistan AI Safety Hub team (KAISH)")
    try:
        send_mail(f["email"], subject, body, reply_to=NOTIFY_EMAIL or None)
        if NOTIFY_EMAIL:
            send_mail(NOTIFY_EMAIL, f"New {form} application: {f.get('full_name', '')}",
                      f"A new {form} application has arrived from {f.get('full_name', '')} ({f.get('email', '')}).")
    except Exception as exc:  # email failure must never lose a submission
        app.logger.warning("Email failed: %s", exc)


# ---------------------------------------------------------------- login
LOCK_AFTER, LOCK_WINDOW, LOCK_FOR = 5, 15 * 60, 15 * 60


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        check_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        con = get_db()
        key = f"{username.lower()}|{request.remote_addr}"
        row = con.execute("SELECT * FROM login_attempts WHERE key = ?", (key,)).fetchone()
        t = time.time()
        if row and row["locked_until"] > t:
            minutes = int((row["locked_until"] - t) // 60) + 1
            error = f"Too many failed attempts. Try again in {minutes} minutes."
        else:
            user = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            ok = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password)
            if user and user["active"] and ok:
                con.execute("DELETE FROM login_attempts WHERE key = ?", (key,))
                con.execute("UPDATE users SET last_login = ? WHERE id = ?", (dbm.now(), user["id"]))
                dbm.log(con, user["id"], "Signed in")
                con.commit()
                session.clear()
                session.permanent = True
                session["uid"], session["tok"], session["uat"] = user["id"], user["session_token"], time.time()
                csrf_token()
                nxt = request.args.get("next", "")
                if user["must_change_password"]:
                    return redirect(url_for("account"))
                return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
            if row and t - row["first_at"] < LOCK_WINDOW:
                failures = row["failures"] + 1
                locked = t + LOCK_FOR if failures >= LOCK_AFTER else 0
                con.execute("UPDATE login_attempts SET failures = ?, locked_until = ? WHERE key = ?", (failures, locked, key))
            else:
                con.execute("INSERT OR REPLACE INTO login_attempts (key, failures, first_at, locked_until) VALUES (?, 1, ?, 0)", (key, t))
            con.commit()
            error = "That username and password don't match. Check them and try again."
    return render_template("admin/login.html", error=error)


@app.post("/logout")
def logout():
    if current_user():
        check_csrf()
        log("Signed out")
        get_db().commit()
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- admin: dashboard
@app.get("/admin")
@login_required
def dashboard():
    if current_user()["role"] == "university":
        return redirect(url_for("uni_home"))
    con = get_db()
    counts = {f: con.execute("SELECT COUNT(*) FROM submissions WHERE form = ?", (f,)).fetchone()[0] for f in FORMS}
    stats = {
        "texts": con.execute("SELECT COUNT(*) FROM texts").fetchone()[0],
        "posts": con.execute("SELECT COUNT(*) FROM posts WHERE published = 1").fetchone()[0],
        "drafts": con.execute("SELECT COUNT(*) FROM posts WHERE published = 0").fetchone()[0],
        "admins": con.execute("SELECT COUNT(*) FROM users WHERE active = 1").fetchone()[0],
        "members": con.execute("SELECT COUNT(*) FROM members").fetchone()[0],
        "universities": con.execute("SELECT COUNT(*) FROM universities").fetchone()[0],
    }
    activity = con.execute(
        "SELECT a.*, u.display_name FROM activity a LEFT JOIN users u ON u.id = a.user_id ORDER BY a.id DESC LIMIT 15").fetchall()
    values = site_values(con)
    empty_settings = sum(1 for k, v in R.load_site()["values"].items()
                         if not (values.get(k) or v).strip() and k not in ("form_endpoint", "domain"))
    return render_template("admin/dashboard.html", counts=counts, stats=stats, activity=activity, apps_open=applications_open(),
                           email_on=email_enabled(), empty_settings=empty_settings, active="dashboard")


# ---------------------------------------------------------------- admin: page texts
KIND_LABELS = {"text": "Text", "option": "List option", "title": "Text", "meta:title": "Browser tab title",
               "meta:description": "Search-engine description", "attr:placeholder": "Placeholder in a box",
               "attr:aria-label": "Screen-reader label", "attr:title": "Tooltip", "attr:alt": "Picture description",
               "attr:data-ineligible": "Message shown on choosing this option"}


NO_PREVIEW = {"news-post", "profile", "profile-edit", "university", "course"}
SPECIAL_TITLES = {"news-post": "News article (shared wording)", "profile": "Member profile (shared wording)",
                  "profile-edit": "Member profile editor", "signin": "Member sign-in", "register": "Member registration",
                  "university": "University page (shared wording)", "course": "Course page (shared wording)"}


def page_title(lang, name):
    if name == "_layout":
        return "Header, footer and shared labels"
    if name in SPECIAL_TITLES:
        return SPECIAL_TITLES[name]
    meta = CATALOG[(lang, name)]["meta"]
    r = R.Renderer(values=site_values(get_db()))
    r.lang = lang
    title = r.fill_plain(meta["title"])
    return re.split(r"\s+·\s+", title)[0] if "·" in title else title


def collect_items(lang, name):
    r = make_renderer(collect=True)
    if name == "_layout":
        return [i for i in r.collect(lang, "index") if i["scope"] == "layout"]
    return [i for i in r.collect(lang, name) if i["scope"] == name]


def save_text(con, lang, item, value, user_id):
    value = R.norm(value)[:5000]
    if not value or value == item["text"]:
        cur = con.execute("DELETE FROM texts WHERE lang = ? AND scope = ? AND key = ?", (lang, item["scope"], item["key"]))
        return cur.rowcount > 0
    old = con.execute("SELECT value FROM texts WHERE lang = ? AND scope = ? AND key = ?",
                      (lang, item["scope"], item["key"])).fetchone()
    if old and old["value"] == value:
        return False
    con.execute("INSERT INTO texts (lang, scope, key, original, value, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (lang, scope, key) DO UPDATE SET value = excluded.value, original = excluded.original, "
                "updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (lang, item["scope"], item["key"], item["text"], value, dbm.now(), user_id))
    return True


def valid_page(lang, name):
    return lang in LANGS and (name == "_layout" or (lang, name) in CATALOG)


@app.get("/admin/pages")
@login_required
def pages():
    con = get_db()
    edited = collections.Counter()
    for r in con.execute("SELECT lang, scope FROM texts"):
        edited[(r["lang"], r["scope"])] += 1
    rows = []
    for lang in LANGS:
        rows.append({"lang": lang, "name": "_layout", "title": page_title(lang, "_layout"), "url": "/" + R.UI[lang]["base"],
                     "edited": edited[(lang, "layout")]})
        for (l, name), info in sorted(CATALOG.items(), key=lambda kv: kv[1]["out"]):
            if l == lang:
                rows.append({"lang": lang, "name": name, "title": page_title(lang, name),
                             "url": info["url"] if name not in NO_PREVIEW else None, "edited": edited[(lang, name)]})
    return render_template("admin/pages.html", rows=rows, active="pages")


@app.route("/admin/pages/<lang>/<name>", methods=["GET", "POST"])
@login_required
def page_texts(lang, name):
    if not valid_page(lang, name):
        abort(404)
    items = collect_items(lang, name)
    if request.method == "POST":
        con, user = get_db(), current_user()
        changed = 0
        for it in items:
            field = f"t|{it['scope']}|{it['key']}"
            if field in request.form and save_text(con, lang, it, request.form[field], user["id"]):
                changed += 1
        if changed:
            log("Edited texts", f"{changed} on {page_title(lang, name)} ({LANG_NAMES[lang]})")
        con.commit()
        flash(f"Saved {changed} change{'s' if changed != 1 else ''}." if changed else "Nothing changed.", "ok")
        return redirect(url_for("page_texts", lang=lang, name=name))
    url = "/" + R.UI[lang]["base"] if name == "_layout" else (CATALOG[(lang, name)]["url"] if name not in NO_PREVIEW else None)
    for it in items:
        it["label"] = KIND_LABELS.get(it["kind"], "Text")
    return render_template("admin/page_texts.html", items=items, lang=lang, name=name, url=url,
                           title=page_title(lang, name), active="pages")


@app.post("/admin/api/texts")
@login_required
def api_texts():
    data = request.get_json(silent=True) or {}
    lang, name = data.get("lang"), data.get("page")
    if not valid_page(lang, name):
        return jsonify(ok=False, error="Unknown page."), 400
    r = make_renderer(collect=True)
    allowed = {f'{i["scope"]}|{i["key"]}': i for i in r.collect(lang, name)}
    con, user = get_db(), current_user()
    saved = 0
    for ch in (data.get("changes") or [])[:3000]:
        it = allowed.get(str(ch.get("t", "")))
        if it and save_text(con, lang, it, str(ch.get("value", "")), user["id"]):
            saved += 1
    if saved:
        log("Edited texts on the page", f"{saved} on {page_title(lang, name)} ({LANG_NAMES[lang]})")
    con.commit()
    return jsonify(ok=True, saved=saved)


# ---------------------------------------------------------------- admin: settings
SETTING_GROUPS = [
    ("Names", [("program_name", "Program name"), ("name_ku", "Hub name in Kurdish, shown in the header")]),
    ("Cohort 1 dates", [("apply_open", "Applications open"), ("apply_deadline", "Applications close"),
                        ("interviews_from", "Conversations start"),
                        ("interviews_to", "Conversations end"), ("decisions_date", "Decisions sent"),
                        ("week0_date", "Welcome meeting"), ("cohort_start", "First session"),
                        ("cohort_end", "Last session"), ("reading_groups_start", "Reading groups start (month and year)")]),
    ("Sessions", [("session_day", "Weekly session day"), ("session_time", "Weekly session time"),
                  ("venue", "Venue in Erbil"), ("cohort_size", "Maximum cohort size")]),
    ("Team recruitment", [("staff_deadline", "Staff applications close"), ("reply_days", "Days to reply to staff applicants"),
                          ("compensation", "Staff compensation (paid, stipended or voluntary)")]),
    ("Contact addresses", [("email_hello", "General email"), ("email_apply", "Applications email"),
                           ("email_team", "Team recruitment email"), ("email_library", "Reading library email")]),
    ("AI Kurd and funding", [("aikurd_url", "AI Kurd website address"), ("aikurd_purpose", "What AI Kurd does"),
                             ("aikurd_audience", "AI Kurd's main audience"), ("aikurd_support", "What AI Kurd provides to the Hub"),
                             ("funding_source", "Who funds the Hub"), ("first_report", "First public report due (month and year)")]),
    ("Team on the About page", [("director_name", "Founder and Director: name"),
                                ("director_background", "Founder and Director: one line of background"),
                                ("member2_name", "Second team member: name"), ("member2_role", "Second team member: role")]),
    ("Privacy notice", [("privacy_updated", "Privacy notice last updated"),
                        ("storage_provider", "Where application data is stored")]),
    ("Homepage picture", [("hero_image_alt", "Short description of the Plate I picture, for screen readers. "
                                              "To change the picture, open the homepage and click Edit this page.")]),
    ("Website", [("domain", "Website address, for search engines (e.g. https://kaish.org)")]),
]
SINGLE_LANGUAGE = {"name_ku", "email_hello", "email_apply", "email_team", "email_library", "aikurd_url", "domain"}


@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    con = get_db()
    defaults = R.load_site()["values"]
    if request.method == "POST":
        changed = 0
        for _group, fields in SETTING_GROUPS:
            for key, _label in fields:
                for k in (key,) if key in SINGLE_LANGUAGE else (key, key + "_ku"):
                    if f"s|{k}" not in request.form:
                        continue
                    v = request.form[f"s|{k}"].strip()[:500]
                    if k == "domain" and v and not re.fullmatch(r"https?://[^\s/]+", v.rstrip("/")):
                        flash("The website address must look like https://example.org.", "warn")
                        continue
                    old = con.execute("SELECT value FROM settings WHERE key = ?", (k,)).fetchone()
                    if (old["value"] if old else defaults.get(k, "")) == v:
                        continue
                    con.execute("INSERT INTO settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?) "
                                "ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, "
                                "updated_by = excluded.updated_by", (k, v, dbm.now(), current_user()["id"]))
                    changed += 1
        if changed:
            log("Updated settings", f"{changed} values")
        con.commit()
        flash(f"Saved {changed} setting{'s' if changed != 1 else ''}." if changed else "Nothing changed.", "ok")
        return redirect(url_for("settings_page"))
    stored = dbm.settings(con)
    current = lambda k: stored.get(k, defaults.get(k, ""))
    return render_template("admin/settings.html", groups=SETTING_GROUPS, single=SINGLE_LANGUAGE,
                           current=current, active="settings")


@app.post("/admin/api/plate")
@login_required
def api_plate():
    """Replace the homepage picture (Plate I), or go back to the woven pattern."""
    con = get_db()
    row = con.execute("SELECT value FROM settings WHERE key = 'hero_image'").fetchone()
    old = row["value"] if row else ""
    if request.form.get("reset") == "1":
        new = ""
    else:
        upload = request.files.get("picture")
        if not upload or not upload.filename:
            return jsonify(ok=False, error="Choose a picture first."), 400
        new, err = save_image(upload)
        if err or not new:
            return jsonify(ok=False, error=err or "That picture couldn't be read."), 400
    con.execute("INSERT INTO settings (key, value, updated_at, updated_by) VALUES ('hero_image', ?, ?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, "
                "updated_by = excluded.updated_by", (new, dbm.now(), current_user()["id"]))
    log("Changed the homepage picture" if new else "Put back the woven homepage pattern")
    con.commit()
    if old and old != new:
        remove_image(old)
    r = make_renderer()
    r.lang, r.prefix = request.form.get("lang", "en"), "/"
    return jsonify(ok=True, html=r.plate_html(), custom=bool(new))


# ---------------------------------------------------------------- admin: news and events
def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60]


def unique_slug(con, base, post_id=None):
    base = base or "post"
    slug, n = base, 2
    while True:
        row = con.execute("SELECT id FROM posts WHERE slug = ?", (slug,)).fetchone()
        if not row or row["id"] == post_id:
            return slug
        slug, n = f"{base}-{n}", n + 1


def save_image(file):
    data = file.read()
    if not data:
        return None, None
    if len(data) > 10 * 1024 * 1024:
        return None, "Pictures must be smaller than 10 MB."
    sig = data[:12]
    if not (sig.startswith(b"\xff\xd8\xff") or sig.startswith(b"\x89PNG") or (sig[:4] == b"RIFF" and sig[8:12] == b"WEBP")):
        return None, "Upload a JPEG, PNG or WebP picture."
    name = secrets.token_hex(12)
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        img.thumbnail((1800, 1800))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        filename = f"{name}.webp"
        img.save(dbm.UPLOADS / filename, "WEBP", quality=84, method=4)
    except ImportError:
        ext = "jpg" if sig.startswith(b"\xff\xd8") else ("png" if sig.startswith(b"\x89PNG") else "webp")
        filename = f"{name}.{ext}"
        (dbm.UPLOADS / filename).write_bytes(data)
    except Exception:
        return None, "That picture couldn't be read. Try saving it again as a JPEG."
    return filename, None


def remove_image(filename):
    if filename and re.fullmatch(r"[a-f0-9]{24}\.(webp|jpg|png)", filename):
        try:
            (dbm.UPLOADS / filename).unlink()
        except FileNotFoundError:
            pass


POST_FIELDS = ("title_en", "title_ku", "summary_en", "summary_ku", "body_en", "body_ku",
               "image_alt_en", "image_alt_ku", "location_en", "location_ku", "event_time")


@app.get("/admin/news")
@login_required
def news_list():
    me = current_user()
    con = get_db()
    order = "ORDER BY COALESCE(NULLIF(published_at, ''), created_at) DESC, id DESC"
    if is_staff(me):
        posts = con.execute(f"SELECT * FROM posts {order}").fetchall()
    else:
        posts = con.execute(f"SELECT * FROM posts WHERE university_id = ? {order}", (me["university_id"],)).fetchall()
    unis = {r["id"]: r for r in con.execute("SELECT * FROM universities")}
    return render_template("admin/news_list.html", posts=posts, unis=unis, fmt=R.fmt_date, active="news")


@app.route("/admin/news/new", methods=["GET", "POST"])
@app.route("/admin/news/<int:post_id>", methods=["GET", "POST"])
@login_required
def news_edit(post_id=None):
    con = get_db()
    me = current_user()
    post = None
    if post_id:
        post = con.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post or (not is_staff(me) and post["university_id"] != me["university_id"]):
            abort(404)
    unis = con.execute("SELECT id, name_en, name_ku, slug FROM universities ORDER BY name_en").fetchall()
    if request.method == "GET":
        return render_template("admin/news_form.html", post=post, unis=unis, active="news")
    f = {k: request.form.get(k, "").strip() for k in POST_FIELDS}
    f["kind"] = "event" if request.form.get("kind") == "event" else "news"
    f["event_date"] = request.form.get("event_date", "").strip()
    f["published_at"] = request.form.get("published_at", "").strip()
    publish = request.form.get("published") == "1"
    errors = []
    if not (f["title_en"] or f["title_ku"]):
        errors.append("Give the post a title in English, Kurdish or both.")
    for k in ("event_date", "published_at"):
        if f[k]:
            try:
                datetime.date.fromisoformat(f[k])
            except ValueError:
                errors.append("Dates must be written as year-month-day, for example 2027-02-07.")
    if f["event_time"] and not re.fullmatch(r"\d{1,2}:\d{2}", f["event_time"]):
        errors.append("Write the time as hours:minutes, for example 17:30.")
    image = post["image"] if post else ""
    upload = request.files.get("image")
    if upload and upload.filename:
        new_image, err = save_image(upload)
        if err:
            errors.append(err)
        elif new_image:
            if image:
                remove_image(image)
            image = new_image
    elif request.form.get("remove_image") == "1" and image:
        remove_image(image)
        image = ""
    if errors:
        for e in errors:
            flash(e, "warn")
        merged = dict(post) if post else {}
        merged.update(f)
        merged["image"], merged["published"] = image, int(publish)
        return render_template("admin/news_form.html", post=merged, unis=unis, active="news"), 400
    if publish and not f["published_at"]:
        f["published_at"] = datetime.date.today().isoformat()
    user = current_user()
    if is_staff(user):
        chosen = request.form.get("university_id", "")
        f["university_id"] = int(chosen) if chosen.isdigit() and any(u["id"] == int(chosen) for u in unis) else None
    else:
        f["university_id"] = user["university_id"]
    slug = unique_slug(con, slugify(f["title_en"]) or (post["slug"] if post else f"post-{int(time.time())}"),
                       post["id"] if post else None)
    cols = list(POST_FIELDS) + ["kind", "event_date", "published_at", "university_id"]
    if post:
        con.execute(f"UPDATE posts SET {', '.join(c + ' = ?' for c in cols)}, slug = ?, image = ?, published = ?, "
                    "updated_at = ?, updated_by = ? WHERE id = ?",
                    [f[c] for c in cols] + [slug, image, int(publish), dbm.now(), user["id"], post["id"]])
        log("Updated a post", f["title_en"] or f["title_ku"])
        pid = post["id"]
    else:
        cur = con.execute(f"INSERT INTO posts ({', '.join(cols)}, slug, image, published, created_at, updated_at, created_by, updated_by) "
                          f"VALUES ({', '.join('?' * (len(cols) + 7))})",
                          [f[c] for c in cols] + [slug, image, int(publish), dbm.now(), dbm.now(), user["id"], user["id"]])
        log("Created a post", f["title_en"] or f["title_ku"])
        pid = cur.lastrowid
    con.commit()
    if f["university_id"]:
        flash("Published on the university's page." if publish else "Saved as a draft. Only admins and the university's representatives can see it.", "ok")
    else:
        flash("Published. It's now on the homepage and the News page." if publish else "Saved as a draft. Only admins can see it.", "ok")
    return redirect(url_for("news_edit", post_id=pid))


@app.post("/admin/news/<int:post_id>/delete")
@login_required
def news_delete(post_id):
    con = get_db()
    post = con.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    me = current_user()
    if not post or (not is_staff(me) and post["university_id"] != me["university_id"]):
        abort(404)
    remove_image(post["image"])
    con.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    log("Deleted a post", post["title_en"] or post["title_ku"])
    con.commit()
    flash("Post deleted.", "ok")
    return redirect(url_for("news_list"))


# ---------------------------------------------------------------- admin: applications
FORM_TITLES = {"cohort": "Cohort 1 applications", "interest": "Next cohort list", "staff": "Team applications", "newsletter": "Mailing list"}


def availability_table(value_lists):
    """Rows of hours by days: how many of the given applicants are free in each hour."""
    sets = [set(v.strip() for v in (vals or "").split(";") if v.strip()) for vals in value_lists]
    days = [d[0] for d in R.AVAIL_DAYS]
    rows, top = [], 0
    for h in R.AVAIL_HOURS:
        cells = [sum(1 for s in sets if f"{d} {h:02d}:00" in s) for d in days]
        top = max([top] + cells)
        rows.append({"label": f"{h:02d}:00", "cells": cells})
    best = sorted(((c, d, r["label"]) for r in rows for d, c in zip(days, r["cells"]) if c), reverse=True)[:5]
    return {"days": days, "rows": rows, "top": top, "people": len(sets), "best": best}


def applications_open():
    row = get_db().execute("SELECT value FROM settings WHERE key = 'applications_open'").fetchone()
    return bool(row) and row["value"] == "1"


@app.post("/admin/applications/state")
@login_required
def applications_state():
    """Open or close Cohort applications. Closed: the Apply buttons become "Get notified about the next cohort"."""
    if not is_staff(current_user()):
        abort(403)
    con = get_db()
    is_open = request.form.get("open") == "1"
    con.execute("INSERT INTO settings (key, value, updated_at, updated_by) VALUES ('applications_open', ?, ?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, "
                "updated_by = excluded.updated_by", ("1" if is_open else "0", dbm.now(), current_user()["id"]))
    log("Opened Cohort applications" if is_open else "Closed Cohort applications")
    con.commit()
    flash("Applications are open. The Apply buttons and the application form are back on the website." if is_open else
          "Applications are closed. Visitors now see “Get notified about the next cohort” and can join the next cohort list.", "ok")
    return redirect(request.form.get("back") if (request.form.get("back") or "").startswith("/admin") else url_for("applications"))


@app.get("/admin/applications")
@login_required
def applications():
    form = request.args.get("form", "cohort")
    if form not in FORMS:
        abort(404)
    con = get_db()
    rows = con.execute("SELECT * FROM submissions WHERE form = ? ORDER BY id DESC", (form,)).fetchall()
    counts = {f: con.execute("SELECT COUNT(*) FROM submissions WHERE form = ?", (f,)).fetchone()[0] for f in FORMS}
    items = []
    for r in rows:
        d = dbm.submission_fields(r)
        items.append({"row": r, "roles": d.get("roles", ""), "city": d.get("city", d.get("location", ""))})
    avail = None
    if form == "cohort":
        lists = [dbm.submission_fields(r).get("availability", "") for r in rows]
        if any(lists):
            avail = availability_table([v for v in lists if v])
    emails = []
    if form == "interest":
        for r in reversed(rows):   # oldest first
            e = (r["email"] or "").strip()
            if e and e.lower() not in {x.lower() for x in emails}:
                emails.append(e)
    return render_template("admin/applications.html", form=form, items=items, counts=counts, avail=avail,
                           titles=FORM_TITLES, apps_open=applications_open(), emails=emails, active="applications")


@app.get("/admin/applications/<int:sub_id>")
@login_required
def application(sub_id):
    row = get_db().execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    if not row:
        abort(404)
    if row["form"].startswith("course:"):
        return redirect(url_for("course_application", sub_id=sub_id))
    fields = dbm.submission_fields(row)
    avail = availability_table([fields["availability"]]) if fields.get("availability") else None
    return render_template("admin/application.html", row=row, fields=fields, avail=avail,
                           titles=FORM_TITLES, active="applications")


@app.post("/admin/applications/<int:sub_id>/delete")
@login_required
def application_delete(sub_id):
    con = get_db()
    row = con.execute("SELECT form, name FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    if not row:
        abort(404)
    con.execute("DELETE FROM submissions WHERE id = ?", (sub_id,))
    log("Deleted an application", f"{FORM_TITLES[row['form']]}: {row['name']}")
    con.commit()
    flash("Deleted.", "ok")
    return redirect(url_for("applications", form=row["form"]))


@app.get("/admin/applications.csv")
@login_required
def applications_csv():
    form = request.args.get("form", "cohort")
    if form not in FORMS:
        abort(404)
    rows = get_db().execute("SELECT * FROM submissions WHERE form = ? ORDER BY id", (form,)).fetchall()
    data = [dbm.submission_fields(r) for r in rows]
    keys = []
    for d in data:
        for k in d:
            if k not in keys:
                keys.append(k)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["received_at"] + keys)
    for r, d in zip(rows, data):
        cells = [d.get(k, "") for k in keys]
        w.writerow([r["created_at"]] + ["'" + c if c[:1] in "=+-@" else c for c in cells])
    log("Downloaded applications", FORM_TITLES[form])
    get_db().commit()
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="kaish-{form}-{datetime.date.today()}.csv"'})


# ---------------------------------------------------------------- admin: accounts
def superadmins_left(con, excluding=None):
    return con.execute("SELECT COUNT(*) FROM users WHERE role = 'superadmin' AND active = 1 AND id != ?",
                       (excluding or 0,)).fetchone()[0]


@app.get("/admin/users")
@superadmin_required
def users():
    rows = get_db().execute("SELECT u.*, c.display_name AS creator, COALESCE(NULLIF(un.name_en, ''), un.name_ku) AS uni_name "
                            "FROM users u LEFT JOIN users c ON c.id = u.created_by LEFT JOIN universities un ON un.id = u.university_id "
                            "ORDER BY u.role = 'university', u.role DESC, u.username").fetchall()
    return render_template("admin/users.html", users=rows, active="users")


@app.post("/admin/users")
@superadmin_required
def user_create():
    con = get_db()
    username = request.form.get("username", "").strip().lower()
    display = request.form.get("display_name", "").strip()[:80]
    role = "superadmin" if request.form.get("role") == "superadmin" else "admin"
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
        flash("Usernames use 3 to 32 lowercase letters, numbers, dots, dashes or underscores.", "warn")
        return redirect(url_for("users"))
    if con.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        flash(f"The username {username} is already taken.", "warn")
        return redirect(url_for("users"))
    pw = temp_password()
    con.execute("INSERT INTO users (username, display_name, password_hash, role, active, must_change_password, "
                "session_token, created_at, created_by) VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?)",
                (username, display or username, generate_password_hash(pw), role, dbm.new_token(), dbm.now(),
                 current_user()["id"]))
    log("Added an admin", f"{username} ({role})")
    con.commit()
    return render_template("admin/password_result.html", username=username, password=pw, created=True, active="users")


def target_user(con, user_id):
    row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        abort(404)
    return row


@app.post("/admin/users/<int:user_id>/reset")
@superadmin_required
def user_reset(user_id):
    con = get_db()
    u = target_user(con, user_id)
    pw = temp_password()
    con.execute("UPDATE users SET password_hash = ?, must_change_password = 1, session_token = ? WHERE id = ?",
                (generate_password_hash(pw), dbm.new_token(), u["id"]))
    log("Reset a password", u["username"])
    con.commit()
    if u["id"] == current_user()["id"]:
        session.clear()
    return render_template("admin/password_result.html", username=u["username"], password=pw, created=False, active="users")


@app.post("/admin/users/<int:user_id>/update")
@superadmin_required
def user_update(user_id):
    con = get_db()
    u = target_user(con, user_id)
    me = current_user()
    role = "superadmin" if request.form.get("role") == "superadmin" else "admin"
    if u["role"] == "university":
        role = "university"
    active = request.form.get("active") == "1"
    if u["id"] == me["id"] and (role != "superadmin" or not active):
        flash("You can't remove your own superadmin access or deactivate yourself.", "warn")
        return redirect(url_for("users"))
    if u["role"] == "superadmin" and (role != "superadmin" or not active) and not superadmins_left(con, u["id"]):
        flash("There must always be at least one active superadmin.", "warn")
        return redirect(url_for("users"))
    token = u["session_token"] if active and u["active"] else dbm.new_token()
    con.execute("UPDATE users SET role = ?, active = ?, session_token = ? WHERE id = ?", (role, int(active), token, u["id"]))
    log("Changed an admin", f"{u['username']}: {role}, {'active' if active else 'deactivated'}")
    con.commit()
    flash(f"Updated {u['username']}.", "ok")
    return redirect(url_for("users"))


@app.post("/admin/users/<int:user_id>/delete")
@superadmin_required
def user_delete(user_id):
    con = get_db()
    u = target_user(con, user_id)
    if u["id"] == current_user()["id"]:
        flash("You can't delete your own account.", "warn")
        return redirect(url_for("users"))
    if u["role"] == "superadmin" and not superadmins_left(con, u["id"]):
        flash("There must always be at least one active superadmin.", "warn")
        return redirect(url_for("users"))
    con.execute("DELETE FROM users WHERE id = ?", (u["id"],))
    log("Deleted an admin", u["username"])
    con.commit()
    flash(f"Deleted {u['username']}.", "ok")
    return redirect(url_for("users"))


@app.route("/admin/account", methods=["GET", "POST"])
@login_required
def account():
    me = current_user()
    if request.method == "POST":
        con = get_db()
        display = request.form.get("display_name", "").strip()[:80] or me["display_name"]
        current, new, confirm = (request.form.get(k, "") for k in ("current", "new", "confirm"))
        if new or me["must_change_password"]:
            problem = None
            if not check_password_hash(me["password_hash"], current):
                problem = "Your current password isn't right."
            elif new != confirm:
                problem = "The two new passwords don't match."
            elif new == current:
                problem = "Choose a password different from the current one."
            else:
                problem = password_problem(new, me["username"])
            if problem:
                flash(problem, "warn")
                return redirect(url_for("account"))
            token = dbm.new_token()
            con.execute("UPDATE users SET password_hash = ?, must_change_password = 0, session_token = ?, display_name = ? WHERE id = ?",
                        (generate_password_hash(new), token, display, me["id"]))
            session["tok"] = token
            log("Changed password")
            flash("Password changed.", "ok")
        else:
            con.execute("UPDATE users SET display_name = ? WHERE id = ?", (display, me["id"]))
            flash("Saved.", "ok")
        con.commit()
        g.pop("user", None)
        return redirect(url_for("dashboard") if not me["must_change_password"] or new else url_for("account"))
    return render_template("admin/account.html", active="account", min_len=MIN_PASSWORD)

# ================================================================ show and hide
HIDEABLE_PAGES = [n for n in ("program", "apply", "resources", "news", "universities", "about", "join-us",
                              "join-us-apply", "privacy")]
SEC_KEY = re.compile(r"[a-z0-9][a-z0-9-]{0,60}")


def page_sections(name):
    """[(key, label)] of the hideable blocks of one page (English labels), or of the header and footer."""
    r = R.Renderer(values=site_values(get_db()), accounts=True)
    html_text = r.render("en", "index" if name == "_layout" else name)
    main_start, main_end = html_text.find('<main id="main">'), html_text.find("</main>")
    items = R.list_sections(html_text)
    if name == "_layout":
        inner = R.list_sections(html_text[main_start:main_end])
        return [i for i in items if i not in inner]
    return R.list_sections(html_text[main_start:main_end])


def set_hidden(con, scope, key, hide):
    if hide:
        con.execute("INSERT OR REPLACE INTO hidden (scope, key, updated_at, updated_by) VALUES (?, ?, ?, ?)",
                    (scope, key, dbm.now(), current_user()["id"]))
    else:
        con.execute("DELETE FROM hidden WHERE scope = ? AND key = ?", (scope, key))


def visibility_groups():
    groups = [("_layout", "Header and footer, on every page")]
    for name in ["index"] + HIDEABLE_PAGES:
        if ("en", name) in CATALOG:
            groups.append((name, page_title("en", name) if name != "index" else "Home page"))
    groups += [("university", "Every university's page"), ("course", "Every course page")]
    return groups


@app.get("/admin/visibility")
@login_required
def visibility():
    hidden = dbm.hidden(get_db())
    pages_list = [{"name": n, "title": page_title("en", n), "url": CATALOG[("en", n)]["url"], "hidden": ("page", n) in hidden}
                  for n in HIDEABLE_PAGES if ("en", n) in CATALOG]
    groups = []
    for name, title in visibility_groups():
        scope = "layout" if name == "_layout" else name
        secs = [{"key": k, "label": l, "hidden": (scope, k) in hidden} for k, l in page_sections(name)]
        groups.append({"name": name, "scope": scope, "title": title, "sections": secs,
                       "count": sum(1 for x in secs if x["hidden"])})
    return render_template("admin/visibility.html", pages=pages_list, groups=groups, active="visibility")


@app.post("/admin/visibility/page")
@login_required
def visibility_page():
    name = request.form.get("name", "")
    if name not in HIDEABLE_PAGES:
        abort(404)
    con = get_db()
    hide = request.form.get("hide") == "1"
    set_hidden(con, "page", name, hide)
    log("Hid a page" if hide else "Showed a page", page_title("en", name))
    con.commit()
    flash(f"{page_title('en', name)} is {'hidden from visitors' if hide else 'visible again'}.", "ok")
    return redirect(url_for("visibility"))


@app.post("/admin/visibility/sections")
@login_required
def visibility_sections():
    name = request.form.get("name", "")
    groups = dict(visibility_groups())
    if name not in groups:
        abort(404)
    scope = "layout" if name == "_layout" else name
    con = get_db()
    shown = set(request.form.getlist("show"))
    changed = 0
    current = dbm.hidden(con)
    for key, _label in page_sections(name):
        hide = key not in shown
        if hide != ((scope, key) in current):
            set_hidden(con, scope, key, hide)
            changed += 1
    if changed:
        log("Changed hidden sections", f"{changed} on {groups[name]}")
    con.commit()
    flash(f"Saved {changed} change{'s' if changed != 1 else ''} to {groups[name]}." if changed else "Nothing changed.", "ok")
    return redirect(url_for("visibility") + f"#g-{name}")


@app.post("/admin/api/sections")
@login_required
def api_sections():
    data = request.get_json(silent=True) or {}
    scope, key, hide = data.get("scope", ""), data.get("key", ""), bool(data.get("hidden"))
    if not SEC_KEY.fullmatch(key) or not (scope == "layout" or ("en", scope) in CATALOG):
        return jsonify(ok=False, error="Unknown section."), 400
    con = get_db()
    set_hidden(con, scope, key, hide)
    log("Hid a section" if hide else "Showed a section", f"{key} ({'header and footer' if scope == 'layout' else page_title('en', scope)})")
    con.commit()
    return jsonify(ok=True, hidden=hide)


# ================================================================ member accounts (public)
# Members are visitors who register on the website. They have a private profile and nothing
# else: member accounts live in their own table and can never open the admin panel.
INTERESTS = ("interp", "evals", "align", "robust", "gov", "ml", "kurdish")
EMAIL_RE = re.compile(r"[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']{2,}")
LINK_RE = re.compile(r"https?://[^\s<>\"']+\.[^\s<>\"']+")
HIDE, SHOW = (" hidden", " hidden"), ("", "")
SIGNIN_ALERTS = ("err_login", "err_locked", "err_expired", "need_signin", "signed_out", "deleted")
REGISTER_ALERTS = ("err_missing", "err_email", "err_taken", "err_short", "err_match", "err_consent", "err_rate", "err_expired")
PROFILE_ALERTS = ("welcome", "saved")
EDIT_ALERTS = ("err_name", "err_link", "err_picture", "err_expired", "pw_changed", "must_change", "err_pw_current",
               "err_pw_short", "err_pw_match", "err_delete")
MEMBER_PHOTO = re.compile(r"[a-f0-9]{24}\.(webp|jpg|png)")


def current_member():
    if "member" in g:
        return g.member
    g.member = None
    mid, tok = session.get("mid"), session.get("mtok")
    if mid and tok:
        row = get_db().execute("SELECT * FROM members WHERE id = ?", (mid,)).fetchone()
        if row and row["active"] and secrets.compare_digest(row["session_token"], tok):
            g.member = row
    return g.member


def start_member_session(member):
    session["mid"], session["mtok"] = member["id"], member["session_token"]
    session["csrf"] = secrets.token_urlsafe(24)
    session.permanent = True
    g.pop("member", None)


def end_member_session():
    session.pop("mid", None)
    session.pop("mtok", None)
    g.pop("member", None)


def csrf_ok():
    sent = request.form.get("csrf", "")
    return bool(sent) and secrets.compare_digest(sent, session.get("csrf", ""))


def lang_url(lang, path=""):
    return ("/ku/" if lang == "ku" else "/") + path


def weak_password(pw):
    return len(pw) < MIN_PASSWORD or len(set(pw)) < 5


def tv(s):
    s = s or ""
    return (H.escape(s), s)


def shown(flag):
    return SHOW if flag else HIDE


def alerts(names, active):
    return {f"show_{n}": shown(n == active) for n in names}


def initials(name):
    words = [w for w in (name or "").split() if w]
    if not words:
        return "?"
    if words[0][0].isascii():
        letters = words[0][0] + (words[-1][0] if len(words) > 1 and words[-1][0].isascii() else "")
        return letters.upper()
    return words[0][0]


def photo_url(member):
    return f"/members/photo/{member['picture']}"


def portrait_html(member):
    if member["picture"]:
        inner = f'<img src="{photo_url(member)}" alt="{H.escape(member["full_name"], quote=True)}">'
    else:
        inner = f'<span class="pf-init" aria-hidden="true">{H.escape(initials(member["full_name"]))}</span>'
    return f'<div class="pf"><div class="pf-thread"><div class="pf-gap"><div class="pf-photo">{inner}</div></div></div></div>'


def avatar_html(member):
    if member["picture"]:
        return f'<span class="av"><img src="{photo_url(member)}" alt=""></span>'
    return f'<span class="av"><span class="av-init" aria-hidden="true">{H.escape(initials(member["full_name"]))}</span></span>'


def registration_open():
    row = get_db().execute("SELECT value FROM settings WHERE key = 'registration_open'").fetchone()
    return not row or row["value"] != "0"


def attempt_lock(con, key):
    """Minutes left on a lock for this sign-in key, or 0."""
    row = con.execute("SELECT * FROM login_attempts WHERE key = ?", (key,)).fetchone()
    t = time.time()
    return int((row["locked_until"] - t) // 60) + 1 if row and row["locked_until"] > t else 0


def record_failure(con, key):
    row = con.execute("SELECT * FROM login_attempts WHERE key = ?", (key,)).fetchone()
    t = time.time()
    if row and t - row["first_at"] < LOCK_WINDOW:
        failures = row["failures"] + 1
        con.execute("UPDATE login_attempts SET failures = ?, locked_until = ? WHERE key = ?",
                    (failures, t + LOCK_FOR if failures >= LOCK_AFTER else 0, key))
    else:
        con.execute("INSERT OR REPLACE INTO login_attempts (key, failures, first_at, locked_until) VALUES (?, 1, ?, 0)", (key, t))
    con.commit()


def account_page(lang, name, tokens):
    """Render one of the member pages (src/pages/NAME.html) with this visitor's values."""
    user = current_user()
    edit = bool(is_staff(user) and name in ("signin", "register") and request.args.get("edit") == "1"
                and not user["must_change_password"])
    r = make_renderer(edit=edit)
    tokens.setdefault("csrf", tv(csrf_token()))
    _meta, body = r.template(lang, name)
    for tok in R.TOKEN.findall(body):
        if tok.startswith("show_") and tok not in tokens:
            tokens[tok] = HIDE
    r.raw.update(tokens)
    head, bar = admin_bar(user, lang, name, edit, editable=name in ("signin", "register")) if user else ("", "")
    return html_response(r.render(lang, name, extra_head=head, extra_body=bar), private=True)


def save_member_photo(file):
    data = file.read(8 * 1024 * 1024 + 1)
    if not data:
        return None, None
    sig = data[:12]
    if len(data) > 8 * 1024 * 1024 or not (sig.startswith(b"\xff\xd8\xff") or sig.startswith(b"\x89PNG")
                                           or (sig[:4] == b"RIFF" and sig[8:12] == b"WEBP")):
        return None, "err_picture"
    name = secrets.token_hex(12)
    try:
        from PIL import Image, ImageOps
        Image.MAX_IMAGE_PIXELS = 40_000_000
        Image.open(io.BytesIO(data)).verify()
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        img = ImageOps.fit(img, (640, 640), Image.LANCZOS, centering=(0.5, 0.42))
        filename = f"{name}.webp"
        img.save(dbm.MEMBER_PHOTOS / filename, "WEBP", quality=85, method=4)
    except ImportError:
        filename = f"{name}." + ("jpg" if sig.startswith(b"\xff\xd8") else "png" if sig.startswith(b"\x89PNG") else "webp")
        (dbm.MEMBER_PHOTOS / filename).write_bytes(data)
    except Exception:
        return None, "err_picture"
    return filename, None


def remove_member_photo(filename):
    if filename and MEMBER_PHOTO.fullmatch(filename):
        try:
            (dbm.MEMBER_PHOTOS / filename).unlink()
        except FileNotFoundError:
            pass


def profile_tokens(m, lang):
    chosen = set(filter(None, m["interests"].split(",")))
    first = (m["full_name"].split() or [""])[0]
    link = ""
    if m["link"]:
        shown_link = re.sub(r"^https?://(www\.)?", "", m["link"]).rstrip("/")
        link = (f'<a href="{H.escape(m["link"], quote=True)}" rel="nofollow noopener" target="_blank" dir="ltr">'
                f'{H.escape(shown_link)}</a>')
    t = {
        "m_portrait": (portrait_html(m), None),
        "m_name": tv(m["full_name"]), "m_first": tv(first),
        "m_name_ku": tv(m["name_ku"]), "show_name_ku": shown(m["name_ku"]),
        "m_occupation": tv(m["occupation"]), "show_occupation": shown(m["occupation"]),
        "m_city": tv(m["city"]), "show_city": shown(m["city"]),
        "m_bio": (R.paragraphs(m["bio"]).replace("<p>", '<p dir="auto">'), None), "show_bio": shown(m["bio"].strip()),
        "m_link": (link, None), "show_link": shown(link),
        "m_since": tv(R.fmt_date(m["created_at"], lang)),
        "show_interests": shown(chosen),
    }
    for k in INTERESTS:
        t[f"show_int_{k}"] = shown(k in chosen)
    return t


def edit_tokens(m, values=None):
    v = dict(m) if values is None else values
    chosen = set(v["interests"]) if values is not None else set(filter(None, m["interests"].split(",")))
    checked = (" checked", " checked")
    t = {
        "m_portrait": (portrait_html(m), None),
        "f_name": tv(v["full_name"]), "f_name_ku": tv(v["name_ku"]), "f_occupation": tv(v["occupation"]),
        "f_city": tv(v["city"]), "f_bio": tv(v["bio"]), "f_link": tv(v["link"]),
        "chk_lang_en": checked if v["language"] != "ku" else SHOW, "chk_lang_ku": checked if v["language"] == "ku" else SHOW,
        "show_remove": shown(m["picture"]),
    }
    for k in INTERESTS:
        t[f"chk_int_{k}"] = checked if k in chosen else SHOW
    return t


def signin_view(lang):
    member = current_member()
    if member and request.method == "GET":
        return redirect(lang_url(lang, "profile"))
    tokens, msg = {"f_email": tv("")}, None
    if request.method == "POST":
        con = get_db()
        email = request.form.get("email", "").strip()[:200]
        tokens["f_email"] = tv(email)
        key = f"m|{email.lower()}|{request.remote_addr}"
        if not csrf_ok():
            msg = "err_expired"
        elif attempt_lock(con, key):
            msg = "err_locked"
        else:
            row = con.execute("SELECT * FROM members WHERE email = ?", (email,)).fetchone()
            ok = check_password_hash(row["password_hash"] if row else DUMMY_HASH, request.form.get("password", ""))
            if row and row["active"] and ok:
                con.execute("DELETE FROM login_attempts WHERE key = ?", (key,))
                con.execute("UPDATE members SET last_login = ? WHERE id = ?", (dbm.now(), row["id"]))
                con.commit()
                start_member_session(row)
                if row["must_change_password"]:
                    return redirect(lang_url(lang, "profile/edit?m=choose#pe-pw"))
                return redirect(lang_url(row["language"] if row["language"] in LANGS else lang, "profile"))
            record_failure(con, key)
            msg = "err_locked" if attempt_lock(con, key) else "err_login"
    else:
        msg = {"out": "signed_out", "deleted": "deleted", "need": "need_signin"}.get(request.args.get("m"))
    tokens.update(alerts(SIGNIN_ALERTS, msg))
    return account_page(lang, "signin", tokens)


def register_view(lang):
    if current_member() and request.method == "GET":
        return redirect(lang_url(lang, "profile"))
    is_open = registration_open()
    tokens = {"f_name": tv(""), "f_email": tv(""), "f_city": tv(""), "show_form": shown(is_open),
              "show_closed": shown(not is_open)}
    msg = None
    if request.method == "POST" and is_open:
        f = request.form
        name, email, city = R.norm(f.get("full_name", ""))[:80], f.get("email", "").strip()[:200], R.norm(f.get("city", ""))[:60]
        pw = f.get("password", "")
        tokens.update({"f_name": tv(name), "f_email": tv(email), "f_city": tv(city)})
        con = get_db()
        if not csrf_ok():
            msg = "err_expired"
        elif f.get("website"):
            return redirect(lang_url(lang, "signin"))  # a bot filled the hidden field
        elif not (name and email and pw):
            msg = "err_missing"
        elif not EMAIL_RE.fullmatch(email):
            msg = "err_email"
        elif weak_password(pw):
            msg = "err_short"
        elif pw != f.get("password2", ""):
            msg = "err_match"
        elif f.get("consent") != "1":
            msg = "err_consent"
        elif rate_limited(f"register|{request.remote_addr}", limit=5, window=3600):
            msg = "err_rate"
        elif con.execute("SELECT 1 FROM members WHERE email = ?", (email,)).fetchone():
            msg = "err_taken"
        else:
            cur = con.execute(
                "INSERT INTO members (email, password_hash, full_name, city, language, session_token, created_at, last_login) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (email, generate_password_hash(pw), name, city, lang, dbm.new_token(), dbm.now(), dbm.now()))
            dbm.log(con, None, "New member", name)
            con.commit()
            start_member_session(con.execute("SELECT * FROM members WHERE id = ?", (cur.lastrowid,)).fetchone())
            return redirect(lang_url(lang, "profile?m=welcome"))
    tokens.update(alerts(REGISTER_ALERTS, msg))
    return account_page(lang, "register", tokens)


def profile_view(lang):
    m = current_member()
    if not m:
        return redirect(lang_url(lang, "signin?m=need"))
    tokens = profile_tokens(m, lang)
    tokens.update(alerts(PROFILE_ALERTS, {"welcome": "welcome", "saved": "saved"}.get(request.args.get("m"))))
    return account_page(lang, "profile", tokens)


def profile_edit_view(lang):
    m = current_member()
    if not m:
        return redirect(lang_url(lang, "signin?m=need"))
    con, msg, values = get_db(), None, None
    if request.method == "POST":
        action = request.form.get("action")
        f = request.form
        if not csrf_ok():
            msg = "err_expired"
        elif action == "profile":
            link = f.get("link", "").strip()[:200]
            if link and not re.match(r"https?://", link, re.I) and re.fullmatch(r"[\w.-]+\.[a-z]{2,}(/\S*)?", link, re.I):
                link = "https://" + link
            values = {
                "full_name": R.norm(f.get("full_name", ""))[:80], "name_ku": R.norm(f.get("name_ku", ""))[:80],
                "occupation": R.norm(f.get("occupation", ""))[:120], "city": R.norm(f.get("city", ""))[:60],
                "bio": re.sub(r"\n{3,}", "\n\n", f.get("bio", "").replace("\r\n", "\n")).strip()[:600], "link": link,
                "language": "ku" if f.get("language") == "ku" else "en",
                "interests": [k for k in INTERESTS if k in f.getlist("interests")],
            }
            if not values["full_name"]:
                msg = "err_name"
            elif link and not LINK_RE.fullmatch(link):
                msg = "err_link"
            new_photo = None
            upload = request.files.get("picture")
            if not msg and upload and upload.filename:
                new_photo, msg = save_member_photo(upload)
            if not msg:
                picture = m["picture"]
                if new_photo or f.get("remove_picture") == "1":
                    remove_member_photo(picture)
                    picture = new_photo or ""
                con.execute("UPDATE members SET full_name = ?, name_ku = ?, occupation = ?, city = ?, bio = ?, link = ?, "
                            "language = ?, interests = ?, picture = ? WHERE id = ?",
                            (values["full_name"], values["name_ku"], values["occupation"], values["city"], values["bio"],
                             values["link"], values["language"], ",".join(values["interests"]), picture, m["id"]))
                con.commit()
                return redirect(lang_url(lang, "profile?m=saved"))
        elif action == "password":
            current, new = f.get("current", ""), f.get("new", "")
            if not check_password_hash(m["password_hash"], current):
                msg = "err_pw_current"
            elif weak_password(new):
                msg = "err_pw_short"
            elif new != f.get("confirm", ""):
                msg = "err_pw_match"
            else:
                token = dbm.new_token()
                con.execute("UPDATE members SET password_hash = ?, session_token = ?, must_change_password = 0 WHERE id = ?",
                            (generate_password_hash(new), token, m["id"]))
                con.commit()
                session["mtok"] = token
                return redirect(lang_url(lang, "profile/edit?m=pw"))
        elif action == "delete":
            if f.get("sure") == "1" and check_password_hash(m["password_hash"], f.get("password", "")):
                remove_member_photo(m["picture"])
                con.execute("DELETE FROM members WHERE id = ?", (m["id"],))
                dbm.log(con, None, "A member deleted their account")
                con.commit()
                end_member_session()
                return redirect(lang_url(lang, "signin?m=deleted"))
            msg = "err_delete"
    else:
        msg = {"pw": "pw_changed", "choose": "must_change"}.get(request.args.get("m"))
        if m["must_change_password"] and not msg:
            msg = "must_change"
    tokens = edit_tokens(m, values)
    tokens.update(alerts(EDIT_ALERTS, msg))
    return account_page(lang, "profile-edit", tokens)


def signout_view(lang):
    if current_member() and csrf_ok():
        end_member_session()
        return redirect(lang_url(lang, "signin?m=out"))
    return redirect(lang_url(lang, "profile"))


for _path, _view, _methods in (("signin", signin_view, ["GET", "POST"]), ("register", register_view, ["GET", "POST"]),
                               ("profile", profile_view, ["GET"]), ("profile/edit", profile_edit_view, ["GET", "POST"]),
                               ("signout", signout_view, ["POST"])):
    for _lang in LANGS:
        _base = "/ku/" if _lang == "ku" else "/"
        _endpoint = f"{_view.__name__}_{_lang}"
        app.add_url_rule(_base + _path, _endpoint, functools.partial(_view, _lang), methods=_methods)
        if _path != "signout":
            app.add_url_rule(_base + _path + ".html", _endpoint + "_html", functools.partial(_view, _lang), methods=_methods)


@app.get("/members/photo/<name>")
def member_photo(name):
    if not MEMBER_PHOTO.fullmatch(name):
        abort(404)
    m = current_member()
    if not ((m and m["picture"] == name) or is_staff(current_user())):
        abort(404)
    resp = send_from_directory(dbm.MEMBER_PHOTOS, name)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp


# ---------------------------------------------------------------- admin: members
@app.get("/admin/members")
@login_required
def members_admin():
    con = get_db()
    q = request.args.get("q", "").strip()[:80]
    sql, args = "SELECT * FROM members", ()
    if q:
        sql += " WHERE full_name LIKE ? OR email LIKE ? OR city LIKE ? OR name_ku LIKE ?"
        args = (f"%{q}%",) * 4
    rows = con.execute(sql + " ORDER BY created_at DESC, id DESC LIMIT 500", args).fetchall()
    total = con.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    return render_template("admin/members.html", members=rows, q=q, total=total, is_open=registration_open(),
                           initials=initials, active="members")


@app.post("/admin/members/registration")
@login_required
def members_registration():
    con = get_db()
    value = "1" if request.form.get("open") == "1" else "0"
    con.execute("INSERT INTO settings (key, value, updated_at, updated_by) VALUES ('registration_open', ?, ?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, "
                "updated_by = excluded.updated_by", (value, dbm.now(), current_user()["id"]))
    log("Opened registration" if value == "1" else "Paused registration")
    con.commit()
    flash("New visitors can create accounts again." if value == "1" else "Registration is paused. Existing members can still sign in.", "ok")
    return redirect(url_for("members_admin"))


def target_member(con, member_id):
    row = con.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not row:
        abort(404)
    return row


@app.get("/admin/members/<int:member_id>")
@login_required
def member_admin(member_id):
    m = target_member(get_db(), member_id)
    chosen = set(filter(None, m["interests"].split(",")))
    labels = {"interp": "Interpretability", "evals": "Evaluations", "align": "Alignment", "robust": "Robustness and security",
              "gov": "AI governance", "ml": "Machine learning foundations", "kurdish": "AI for the Kurdish language"}
    return render_template("admin/member.html", m=m, interests=[labels[k] for k in INTERESTS if k in chosen],
                           portrait=portrait_html(m), fmt=R.fmt_date, active="members")


@app.post("/admin/members/<int:member_id>/reset")
@login_required
def member_reset(member_id):
    con = get_db()
    m = target_member(con, member_id)
    pw = temp_password()
    con.execute("UPDATE members SET password_hash = ?, must_change_password = 1, session_token = ? WHERE id = ?",
                (generate_password_hash(pw), dbm.new_token(), m["id"]))
    con.execute("DELETE FROM login_attempts WHERE key LIKE ?", (f"m|{m['email'].lower()}|%",))
    log("Reset a member's password", m["email"])
    con.commit()
    return render_template("admin/member_password.html", m=m, password=pw, active="members")


@app.post("/admin/members/<int:member_id>/active")
@login_required
def member_active(member_id):
    con = get_db()
    m = target_member(con, member_id)
    active = request.form.get("active") == "1"
    con.execute("UPDATE members SET active = ?, session_token = ? WHERE id = ?",
                (int(active), m["session_token"] if active else dbm.new_token(), m["id"]))
    log("Reactivated a member" if active else "Paused a member", m["email"])
    con.commit()
    flash(f"{m['full_name']} can sign in again." if active else f"{m['full_name']} is paused and signed out.", "ok")
    return redirect(url_for("member_admin", member_id=m["id"]))


@app.post("/admin/members/<int:member_id>/delete")
@login_required
def member_delete(member_id):
    con = get_db()
    m = target_member(con, member_id)
    remove_member_photo(m["picture"])
    con.execute("DELETE FROM members WHERE id = ?", (m["id"],))
    log("Deleted a member", m["email"])
    con.commit()
    flash(f"Deleted {m['full_name']}'s account.", "ok")
    return redirect(url_for("members_admin"))



# ================================================================ universities
# Each university has one page (its name can only be added once), run by its own representatives:
# accounts with the "university" role, which can edit their page, post news and events, and open
# courses with their own application forms. They can't reach anything else in the admin panel.
QTYPES = {"text": "Short answer", "long": "Long answer", "choice": "One choice", "multi": "Several choices",
          "availability": "Weekly availability table"}
UNI_UI = {
    "en": {"optional": "optional", "apply_by": "Apply by", "starts": "Starts", "where": "Where", "closed": "Applications closed",
           "website": "Website", "draft_uni": "Draft: only admins and this university's representatives can see this page.",
           "draft_course": "Draft: only admins and this university's representatives can see this course."},
    "ku": {"optional": "ئارەزوومەندانە", "apply_by": "دوا وادە", "starts": "دەستپێک", "where": "شوێن", "closed": "وەرگرتنی داواکاری داخراوە",
           "website": "ماڵپەڕ", "draft_uni": "ڕەشنووس: تەنها بەڕێوەبەران و نوێنەرانی ئەم زانکۆیە ئەم پەڕەیە دەبینن.",
           "draft_course": "ڕەشنووس: تەنها بەڕێوەبەران و نوێنەرانی ئەم زانکۆیە ئەم کۆرسە دەبینن."},
}
UNI_PATH = re.compile(r"^([a-z0-9][a-z0-9-]{0,80})(?:\.html)?$")
COURSE_PATH = re.compile(r"^([a-z0-9][a-z0-9-]{0,80})/courses/([a-z0-9][a-z0-9-]{0,80})(?:\.html)?$")


def name_key(name):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", name or "").casefold())


def pick(row, field, lang):
    """A bilingual field in this language, falling back to the other one."""
    own = (row[f"{field}_{lang}"] or "").strip()
    if own:
        return own
    return (row[f"{field}_{'ku' if lang == 'en' else 'en'}"] or "").strip()


def uni_name(u, lang):
    return pick(u, "name", lang)


def can_manage_uni(user, uni_id):
    return is_staff(user) or (user and user["role"] == "university" and user["university_id"] == uni_id)


def uni_logo(u, size=56):
    if u["logo"]:
        return f'<img src="/uploads/{H.escape(u["logo"], quote=True)}" alt="" width="{size}" height="{size}">'
    return R.orn.mark_svg(size)


def course_is_open(c):
    if not (c["published"] and c["accepting"]):
        return False
    if c["deadline"]:
        try:
            return datetime.date.fromisoformat(c["deadline"]) >= datetime.date.today()
        except ValueError:
            return True
    return True


def open_course(con, course_id):
    c = con.execute("SELECT c.*, u.published AS uni_published FROM courses c JOIN universities u ON u.id = c.university_id "
                    "WHERE c.id = ?", (course_id,)).fetchone()
    if not c or not c["uni_published"] or not course_is_open(c):
        return None
    if ("page", "universities") in dbm.hidden(con):
        return None
    return c


def course_questions(c):
    try:
        qs = json.loads(c["questions"] or "[]")
        return qs if isinstance(qs, list) else []
    except ValueError:
        return []


def q_text(q, field, lang):
    own = (q.get(f"{field}_{lang}") or "").strip()
    return own or (q.get(f"{field}_{'ku' if lang == 'en' else 'en'}") or "").strip()


def render_questions(questions, lang):
    ui = UNI_UI[lang]
    out = []
    for q in questions:
        qid, t = q["id"], q["type"]
        label = H.escape(q_text(q, "label", lang))
        help_text = q_text(q, "help", lang)
        req = bool(q.get("required"))
        mark = '<span class="req" aria-hidden="true">*</span>' if req else f'<span class="opt-tag">{ui["optional"]}</span>'
        help_html = f'<p class="help" id="h-{qid}">{H.escape(help_text)}</p>' if help_text else ""
        described = f' aria-describedby="h-{qid}"' if help_text else ""
        required = " required" if req else ""
        if t in ("text", "long"):
            ctrl = (f'<textarea id="f-{qid}" name="{qid}" class="short" dir="auto"{described}{required}></textarea>' if t == "long"
                    else f'<input id="f-{qid}" name="{qid}" type="text" dir="auto"{described}{required}>')
            out.append(f'<div class="field"><label for="f-{qid}">{label}{mark}</label>{help_html}{ctrl}</div>')
        elif t in ("choice", "multi"):
            kind = "radio" if t == "choice" else "checkbox"
            opts = []
            for i, o in enumerate(q.get("options") or []):
                value = (o.get("en") or o.get("ku") or "").strip()
                shown = (o.get(lang) or value).strip()
                opts.append(f'<label class="opt" for="f-{qid}-{i}"><input id="f-{qid}-{i}" type="{kind}" name="{qid}" '
                            f'value="{H.escape(value, quote=True)}">{H.escape(shown)}</label>')
            group = f' data-required-group="{qid}"' if req else ""
            out.append(f'<fieldset class="field"{group}><legend class="q">{label}{mark}</legend>{help_html}'
                       f'<div class="opts">{"".join(opts)}</div></fieldset>')
        elif t == "availability":
            group = ' data-required-group="availability"' if req else ""
            out.append(f'<fieldset class="field avail-field"{group}><legend class="q">{label}{mark}</legend>{help_html}'
                       f'{R.availability_grid(lang)}</fieldset>')
    return "".join(out)


def clean_questions(raw, old=None):
    """Validate the question list sent by the course editor. Keeps ids stable so answers stay matched."""
    try:
        items = json.loads(raw or "[]")
    except ValueError:
        return None, "The questions couldn't be read. Reload the page and try again."
    if not isinstance(items, list) or len(items) > 40:
        return None, "A course can have up to 40 questions."
    used = {q.get("id") for q in (old or []) if isinstance(q, dict)}
    taken, out, avail = set(), [], False
    next_n = 1 + max([int(i[1:]) for i in used if isinstance(i, str) and re.fullmatch(r"q\d{1,4}", i)] + [0])
    for q in items:
        if not isinstance(q, dict) or q.get("type") not in QTYPES:
            continue
        t = q["type"]
        clean = {"type": t, "required": bool(q.get("required"))}
        for f, limit in (("label_en", 300), ("label_ku", 300), ("help_en", 500), ("help_ku", 500)):
            clean[f] = R.norm(str(q.get(f) or ""))[:limit]
        if not (clean["label_en"] or clean["label_ku"]):
            return None, "Every question needs a question text, in English, Kurdish or both."
        if t == "availability":
            if avail:
                return None, "A form can have only one weekly availability table."
            avail, clean["id"] = True, "availability"
        else:
            qid = q.get("id")
            if not (isinstance(qid, str) and re.fullmatch(r"q\d{1,4}", qid) and qid not in taken):
                qid, next_n = f"q{next_n}", next_n + 1
            clean["id"] = qid
        taken.add(clean["id"])
        if t in ("choice", "multi"):
            opts = []
            for o in (q.get("options") or [])[:30]:
                if isinstance(o, dict):
                    en, ku = R.norm(str(o.get("en") or ""))[:200], R.norm(str(o.get("ku") or ""))[:200]
                    if en or ku:
                        opts.append({"en": en, "ku": ku})
            if len(opts) < 2:
                return None, f"“{clean['label_en'] or clean['label_ku']}” needs at least two options."
            clean["options"] = opts
        out.append(clean)
    return out, None


def uni_lang_paths(lang, out):
    """(prefix back to the site root, root of this language) for a page written at `out`."""
    full = R.UI[lang]["base"] + out
    prefix = "../" * full.count("/")
    return prefix, prefix + R.UI[lang]["base"]


def uni_page_response(lang, name, tokens, out=None):
    user = current_user()
    edit = bool(is_staff(user) and request.args.get("edit") == "1" and not user["must_change_password"])
    r = make_renderer(edit=edit)
    r.lang = lang
    if callable(tokens.get("_build")):
        tokens.update(tokens.pop("_build")(r))
    r.raw.update(tokens)
    head, bar = admin_bar(user, lang, name, edit) if user else ("", "")
    return html_response(r.render(lang, name, extra_head=head, extra_body=bar, out=out), private=bool(user or current_member()))


def universities_hidden_for(user):
    return not is_staff(user) and ("page", "universities") in dbm.hidden(get_db())


def universities_view(lang):
    user = current_user()
    if universities_hidden_for(user):
        abort(404)
    con = get_db()
    unis = con.execute("SELECT * FROM universities WHERE published = 1 ORDER BY name_en COLLATE NOCASE").fetchall()
    counts = collections.Counter()
    for c in con.execute("SELECT * FROM courses WHERE published = 1"):
        if course_is_open(c):
            counts[c["university_id"]] += 1
    _prefix, root = uni_lang_paths(lang, "universities.html")
    loc = (lambda t: str(t).translate(R.KU_DIGITS)) if lang == "ku" else str

    def build(r):
        skeleton = r.uni_card_skeleton()
        cards = []
        for u in unis:
            name = uni_name(u, lang)
            other = pick(u, "name", "ku" if lang == "en" else "en")
            cards.append(r.fill_skeleton(skeleton, {
                "card_href": f"{root}universities/{u['slug']}", "card_logo": uni_logo(u, 52),
                "card_name": R.braces(H.escape(name)), "card_alt": R.braces(H.escape(other if other != name else "")),
                "card_city": R.braces(H.escape(pick(u, "city", lang))), "card_count": loc(counts[u["id"]])}))
        return {"uni_list": (f'<div class="uni-grid">{"".join(cards)}</div>' if cards else "", None)}

    tokens = {"_build": build, "uni_empty": (" hidden", " hidden") if unis else ("", "")}
    return uni_page_response(lang, "universities", tokens)


def university_tokens(con, u, lang, root, prefix):
    ui = UNI_UI[lang]
    name = uni_name(u, lang)
    other = pick(u, "name", "ku" if lang == "en" else "en")
    about = pick(u, "about", lang)
    facts = []
    city = pick(u, "city", lang)
    if city:
        facts.append(f"<span>{H.escape(city)}</span>")
    if u["website"]:
        site = re.sub(r"^https?://(www\.)?", "", u["website"]).rstrip("/")
        facts.append(f'<a href="{H.escape(u["website"], quote=True)}" rel="noopener" target="_blank" dir="ltr">{H.escape(site)}</a>')
    return {
        "uni_name": tv(name), "uni_alt": tv(other if other != name else ""),
        "uni_alt_hidden": shown(other and other != name), "uni_logo": (uni_logo(u, 88), None),
        "uni_facts": ("".join(facts), None), "uni_href": tv(f"{root}universities/{u['slug']}"),
        "uni_about": (R.paragraphs(about).replace("<p>", '<p dir="auto">'), None), "uni_about_hidden": shown(about),
        "uni_draft": (f'<p class="note">{H.escape(ui["draft_uni"])}</p>' if not u["published"] else "", None),
    }


def course_facts(c, lang):
    ui = UNI_UI[lang]
    facts = []
    if c["deadline"]:
        facts.append(f'{ui["apply_by"]}: {R.fmt_date(c["deadline"], lang)}')
    if c["starts"]:
        facts.append(f'{ui["starts"]}: {c["starts"].translate(R.KU_DIGITS) if lang == "ku" else c["starts"]}')
    where = pick(c, "location", lang)
    if where:
        facts.append(f'{ui["where"]}: {where}')
    return facts


def university_view(lang, slug):
    user = current_user()
    if universities_hidden_for(user):
        abort(404)
    con = get_db()
    u = con.execute("SELECT * FROM universities WHERE slug = ?", (slug,)).fetchone()
    if not u or not (u["published"] or can_manage_uni(user, u["id"])):
        abort(404)
    out = f"universities/{u['slug']}.html"
    prefix, root = uni_lang_paths(lang, out)
    courses = con.execute("SELECT * FROM courses WHERE university_id = ? AND published = 1 ORDER BY id DESC", (u["id"],)).fetchall()
    # open courses first, soonest deadline first; then closed ones, most recent first
    courses = sorted(courses, key=lambda c: (not course_is_open(c), (c["deadline"] or "9999") if course_is_open(c) else ""))
    posts = dbm.published_posts(con, u["id"])

    def build(r):
        skeleton = r.course_card_skeleton()
        cards = []
        for c in courses:
            cards.append(r.fill_skeleton(skeleton, {
                "card_open": "1" if course_is_open(c) else "0",
                "card_href": f"{root}universities/{u['slug']}/courses/{c['slug']}",
                "card_title": R.braces(H.escape(pick(c, "title", lang))),
                "card_summary": R.braces(H.escape(pick(c, "summary", lang))),
                "card_facts": "".join(f"<span>{R.braces(H.escape(f))}</span>" for f in course_facts(c, lang))}))
        r.posts = posts
        r.lang = lang
        news = f'<div class="news-grid">{r.cards(posts, prefix)}</div>' if posts else ""
        return {"uni_courses": (f'<div class="course-grid">{"".join(cards)}</div>' if cards else "", None),
                "uni_news": (news, None)}

    tokens = university_tokens(con, u, lang, root, prefix)
    tokens.update({"_build": build, "uni_courses_empty": shown(not courses), "uni_news_empty": shown(not posts)})
    return uni_page_response(lang, "university", tokens, out=out)


def course_view(lang, slug, cslug):
    user = current_user()
    if universities_hidden_for(user):
        abort(404)
    con = get_db()
    u = con.execute("SELECT * FROM universities WHERE slug = ?", (slug,)).fetchone()
    if not u:
        abort(404)
    c = con.execute("SELECT * FROM courses WHERE university_id = ? AND slug = ?", (u["id"], cslug)).fetchone()
    manage = can_manage_uni(user, u["id"])
    if not c or not ((u["published"] and c["published"]) or manage):
        abort(404)
    out = f"universities/{u['slug']}/courses/{c['slug']}.html"
    prefix, root = uni_lang_paths(lang, out)
    is_open = course_is_open(c) and u["published"]
    summary, details = pick(c, "summary", lang), pick(c, "details", lang)
    facts = course_facts(c, lang)
    tokens = university_tokens(con, u, lang, root, prefix)
    tokens.update({
        "course_title": tv(pick(c, "title", lang)), "course_summary": tv(summary), "course_summary_hidden": shown(summary),
        "course_facts": ("".join(f"<span>{H.escape(f)}</span>" for f in facts), None),
        "course_aside": ("".join(f"<li>{H.escape(f)}</li>" for f in facts) or f"<li>{H.escape(uni_name(u, lang))}</li>", None),
        "course_details": (R.paragraphs(details).replace("<p>", '<p dir="auto">'), None), "course_details_hidden": shown(details),
        "course_closed": shown(not is_open), "course_open": shown(is_open),
        "course_form": tv(f"course:{c['id']}"), "course_questions": (render_questions(course_questions(c), lang), None),
        "course_draft": (f'<p class="note">{H.escape(UNI_UI[lang]["draft_course"])}</p>' if not (c["published"] and u["published"]) else "", None),
    })
    return uni_page_response(lang, "course", tokens, out=out)


def universities_router(lang, rest=""):
    if request.path.endswith("/"):
        return redirect(request.path.rstrip("/"), 301)
    if not rest:
        return universities_view(lang)
    m = COURSE_PATH.match(rest)
    if m:
        return course_view(lang, m.group(1), m.group(2))
    m = UNI_PATH.match(rest)
    if m:
        return university_view(lang, m.group(1))
    abort(404)


for _lang in LANGS:
    _base = "/ku/" if _lang == "ku" else "/"
    for _i, _rule in enumerate(("universities", "universities.html", "universities/<path:rest>")):
        app.add_url_rule(_base + _rule, f"universities_{_lang}_{_i}", functools.partial(universities_router, _lang),
                         strict_slashes=False if _i == 0 else None)


# ---------------------------------------------------------------- admin: universities (staff)
@app.get("/admin/universities")
@login_required
def universities_admin():
    con = get_db()
    unis = con.execute("SELECT * FROM universities ORDER BY name_en COLLATE NOCASE").fetchall()
    stats = {}
    for u in unis:
        stats[u["id"]] = {
            "courses": con.execute("SELECT COUNT(*) FROM courses WHERE university_id = ?", (u["id"],)).fetchone()[0],
            "reps": con.execute("SELECT COUNT(*) FROM users WHERE university_id = ?", (u["id"],)).fetchone()[0],
            "posts": con.execute("SELECT COUNT(*) FROM posts WHERE university_id = ?", (u["id"],)).fetchone()[0]}
    return render_template("admin/universities.html", unis=unis, stats=stats, active="universities")


def name_taken(con, name_en, name_ku, exclude=None):
    keys = {k for k in (name_key(name_en), name_key(name_ku)) if k}
    for row in con.execute("SELECT id, name_en, name_ku FROM universities"):
        if row["id"] == exclude:
            continue
        if keys & {k for k in (name_key(row["name_en"]), name_key(row["name_ku"])) if k}:
            return row
    return None


@app.post("/admin/universities")
@login_required
def university_create():
    con = get_db()
    name_en = R.norm(request.form.get("name_en", ""))[:120]
    name_ku = R.norm(request.form.get("name_ku", ""))[:120]
    city_en = R.norm(request.form.get("city_en", ""))[:60]
    if not (name_en or name_ku):
        flash("Write the university's name in English, Kurdish or both.", "warn")
        return redirect(url_for("universities_admin"))
    clash = name_taken(con, name_en, name_ku)
    if clash:
        flash(f"{clash['name_en'] or clash['name_ku']} already has a page. Each university can be added only once.", "warn")
        return redirect(url_for("universities_admin"))
    base = slugify(name_en) or f"university-{int(time.time())}"
    slug, n = base, 2
    while con.execute("SELECT 1 FROM universities WHERE slug = ?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    cur = con.execute("INSERT INTO universities (slug, name_en, name_ku, name_key, city_en, published, created_at, updated_at) "
                      "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                      (slug, name_en, name_ku, name_key(name_en or name_ku), city_en, dbm.now(), dbm.now()))
    log("Added a university", name_en or name_ku)
    con.commit()
    flash("University added. Add its details, then an account for its representatives.", "ok")
    return redirect(url_for("uni_edit", uni_id=cur.lastrowid))


def target_uni(con, uni_id):
    u = con.execute("SELECT * FROM universities WHERE id = ?", (uni_id,)).fetchone()
    if not u or not can_manage_uni(current_user(), u["id"]):
        abort(404)
    return u


UNI_FIELDS = ("name_en", "name_ku", "city_en", "city_ku", "about_en", "about_ku")


@app.route("/admin/universities/<int:uni_id>", methods=["GET", "POST"])
@login_required
def uni_edit(uni_id):
    con = get_db()
    u = target_uni(con, uni_id)
    me = current_user()
    if request.method == "POST":
        f = {k: (request.form.get(k, "").strip() if k.startswith("about") else R.norm(request.form.get(k, "")))[:3000 if k.startswith("about") else 120]
             for k in UNI_FIELDS}
        website = request.form.get("website", "").strip()[:200]
        if website and not re.match(r"https?://", website, re.I):
            website = "https://" + website
        problems = []
        if not (f["name_en"] or f["name_ku"]):
            problems.append("The university needs a name.")
        elif name_taken(con, f["name_en"], f["name_ku"], exclude=u["id"]):
            problems.append("Another university already uses that name.")
        if website and not re.fullmatch(r"https?://[^\s<>\"']+\.[^\s<>\"']+", website):
            problems.append("The website address doesn't look right.")
        logo = u["logo"]
        upload = request.files.get("logo")
        if not problems:
            if upload and upload.filename:
                new_logo, err = save_image(upload)
                if err:
                    problems.append(err)
                elif new_logo:
                    remove_image(logo)
                    logo = new_logo
            elif request.form.get("remove_logo") == "1" and logo:
                remove_image(logo)
                logo = ""
        if problems:
            for msg in problems:
                flash(msg, "warn")
            return redirect(url_for("uni_edit", uni_id=u["id"]))
        published = (request.form.get("published") == "1") if is_staff(me) else bool(u["published"])
        con.execute(f"UPDATE universities SET {', '.join(k + ' = ?' for k in UNI_FIELDS)}, name_key = ?, website = ?, logo = ?, "
                    "published = ?, updated_at = ? WHERE id = ?",
                    [f[k] for k in UNI_FIELDS] + [name_key(f["name_en"] or f["name_ku"]), website, logo, int(published), dbm.now(), u["id"]])
        log("Updated a university page", f["name_en"] or f["name_ku"])
        con.commit()
        flash("Saved.", "ok")
        return redirect(url_for("uni_edit", uni_id=u["id"]))
    reps = con.execute("SELECT * FROM users WHERE university_id = ? ORDER BY username", (u["id"],)).fetchall()
    return render_template("admin/university.html", u=u, reps=reps, active="universities" if is_staff(me) else "uni_page")


@app.post("/admin/universities/<int:uni_id>/reps")
@login_required
def uni_rep_create(uni_id):
    con = get_db()
    u = target_uni(con, uni_id)
    if not is_staff(current_user()):
        abort(403)
    username = request.form.get("username", "").strip().lower()
    display = R.norm(request.form.get("display_name", ""))[:80]
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
        flash("Usernames use 3 to 32 lowercase letters, numbers, dots, dashes or underscores.", "warn")
        return redirect(url_for("uni_edit", uni_id=u["id"]))
    if con.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        flash(f"The username {username} is already taken.", "warn")
        return redirect(url_for("uni_edit", uni_id=u["id"]))
    pw = temp_password()
    dbm.create_user(con, username, display or username, generate_password_hash(pw), "university", True, current_user()["id"])
    con.execute("UPDATE users SET university_id = ? WHERE username = ?", (u["id"], username))
    log("Added a university representative", f"{username} ({u['name_en'] or u['name_ku']})")
    con.commit()
    return render_template("admin/password_result.html", username=username, password=pw, created=True,
                           back=url_for("uni_edit", uni_id=u["id"]), active="universities")


def target_rep(con, u, user_id):
    rep = con.execute("SELECT * FROM users WHERE id = ? AND university_id = ? AND role = 'university'", (user_id, u["id"])).fetchone()
    if not rep or not is_staff(current_user()):
        abort(404)
    return rep


@app.post("/admin/universities/<int:uni_id>/reps/<int:user_id>/reset")
@login_required
def uni_rep_reset(uni_id, user_id):
    con = get_db()
    u = target_uni(con, uni_id)
    rep = target_rep(con, u, user_id)
    pw = temp_password()
    con.execute("UPDATE users SET password_hash = ?, must_change_password = 1, session_token = ? WHERE id = ?",
                (generate_password_hash(pw), dbm.new_token(), rep["id"]))
    log("Reset a password", rep["username"])
    con.commit()
    return render_template("admin/password_result.html", username=rep["username"], password=pw, created=False,
                           back=url_for("uni_edit", uni_id=u["id"]), active="universities")


@app.post("/admin/universities/<int:uni_id>/reps/<int:user_id>/delete")
@login_required
def uni_rep_delete(uni_id, user_id):
    con = get_db()
    u = target_uni(con, uni_id)
    rep = target_rep(con, u, user_id)
    con.execute("DELETE FROM users WHERE id = ?", (rep["id"],))
    log("Removed a university representative", rep["username"])
    con.commit()
    flash(f"Removed {rep['username']}.", "ok")
    return redirect(url_for("uni_edit", uni_id=u["id"]))


@app.post("/admin/universities/<int:uni_id>/delete")
@login_required
def uni_delete(uni_id):
    con = get_db()
    u = target_uni(con, uni_id)
    if not is_staff(current_user()):
        abort(403)
    for c in con.execute("SELECT id FROM courses WHERE university_id = ?", (u["id"],)).fetchall():
        con.execute("DELETE FROM submissions WHERE form = ?", (f"course:{c['id']}",))
    con.execute("DELETE FROM courses WHERE university_id = ?", (u["id"],))
    for p in con.execute("SELECT image FROM posts WHERE university_id = ?", (u["id"],)).fetchall():
        remove_image(p["image"])
    con.execute("DELETE FROM posts WHERE university_id = ?", (u["id"],))
    con.execute("DELETE FROM users WHERE university_id = ? AND role = 'university'", (u["id"],))
    remove_image(u["logo"])
    con.execute("DELETE FROM universities WHERE id = ?", (u["id"],))
    log("Deleted a university", u["name_en"] or u["name_ku"])
    con.commit()
    flash(f"Deleted {u['name_en'] or u['name_ku']} with its courses, applications, posts and representative accounts.", "ok")
    return redirect(url_for("universities_admin"))


# ---------------------------------------------------------------- university panel
@app.get("/admin/uni")
@login_required
def uni_home():
    me = current_user()
    if is_staff(me):
        return redirect(url_for("universities_admin"))
    con = get_db()
    u = con.execute("SELECT * FROM universities WHERE id = ?", (me["university_id"],)).fetchone()
    if not u:
        return render_template("admin/message.html", title="No university",
                               text="This account isn't linked to a university any more. Ask the Hub team for help.",
                               link="/", link_text="Go to the website")
    courses = con.execute("SELECT * FROM courses WHERE university_id = ? ORDER BY id DESC", (u["id"],)).fetchall()
    apps = {c["id"]: con.execute("SELECT COUNT(*) FROM submissions WHERE form = ?", (f"course:{c['id']}",)).fetchone()[0] for c in courses}
    posts = con.execute("SELECT COUNT(*) FROM posts WHERE university_id = ?", (u["id"],)).fetchone()[0]
    return render_template("admin/uni_home.html", u=u, courses=courses, apps=apps, posts=posts,
                           is_open=course_is_open, active="uni_home")


@app.get("/admin/universities/<int:uni_id>/courses")
@login_required
def uni_courses(uni_id):
    con = get_db()
    u = target_uni(con, uni_id)
    courses = con.execute("SELECT * FROM courses WHERE university_id = ? ORDER BY id DESC", (u["id"],)).fetchall()
    apps = {c["id"]: con.execute("SELECT COUNT(*) FROM submissions WHERE form = ?", (f"course:{c['id']}",)).fetchone()[0] for c in courses}
    return render_template("admin/uni_courses.html", u=u, courses=courses, apps=apps, is_open=course_is_open,
                           fmt=R.fmt_date, active="universities" if is_staff(current_user()) else "uni_courses")


COURSE_FIELDS = ("title_en", "title_ku", "summary_en", "summary_ku", "details_en", "details_ku", "location_en", "location_ku", "starts")


def target_course(con, course_id):
    c = con.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not c or not can_manage_uni(current_user(), c["university_id"]):
        abort(404)
    return c


@app.route("/admin/universities/<int:uni_id>/courses/new", methods=["GET", "POST"])
@app.route("/admin/courses/<int:course_id>", methods=["GET", "POST"])
@login_required
def course_edit(uni_id=None, course_id=None):
    con = get_db()
    c = target_course(con, course_id) if course_id else None
    u = target_uni(con, c["university_id"] if c else uni_id)
    active = "universities" if is_staff(current_user()) else "uni_courses"
    if request.method == "GET":
        return render_template("admin/course_form.html", u=u, c=c, questions=course_questions(c) if c else [],
                               qtypes=QTYPES, active=active)
    f = {k: (request.form.get(k, "").strip()[:4000] if k.startswith("details") else R.norm(request.form.get(k, ""))[:300]) for k in COURSE_FIELDS}
    deadline = request.form.get("deadline", "").strip()
    questions, problem = clean_questions(request.form.get("questions", "[]"), course_questions(c) if c else [])
    problems = [problem] if problem else []
    if not (f["title_en"] or f["title_ku"]):
        problems.append("Give the course a title in English, Kurdish or both.")
    if deadline:
        try:
            datetime.date.fromisoformat(deadline)
        except ValueError:
            problems.append("Write the deadline as year-month-day, for example 2027-02-07.")
    if problems:
        for p in problems:
            flash(p, "warn")
        draft = dict(c) if c else {"id": None}
        draft.update(f)
        draft.update({"deadline": deadline, "accepting": int(request.form.get("accepting") == "1"),
                      "published": int(request.form.get("published") == "1")})
        try:
            raw_q = json.loads(request.form.get("questions", "[]"))
        except ValueError:
            raw_q = []
        return render_template("admin/course_form.html", u=u, c=draft, questions=raw_q if isinstance(raw_q, list) else [],
                               qtypes=QTYPES, active=active), 400
    base = slugify(f["title_en"]) or (c["slug"] if c else f"course-{int(time.time())}")
    slug, n = base, 2
    while True:
        row = con.execute("SELECT id FROM courses WHERE university_id = ? AND slug = ?", (u["id"], slug)).fetchone()
        if not row or (c and row["id"] == c["id"]):
            break
        slug, n = f"{base}-{n}", n + 1
    values = [f[k] for k in COURSE_FIELDS] + [deadline, json.dumps(questions, ensure_ascii=False),
                                              int(request.form.get("accepting") == "1"), int(request.form.get("published") == "1"), slug]
    if c:
        con.execute(f"UPDATE courses SET {', '.join(k + ' = ?' for k in COURSE_FIELDS)}, deadline = ?, questions = ?, accepting = ?, "
                    "published = ?, slug = ?, updated_at = ? WHERE id = ?", values + [dbm.now(), c["id"]])
        cid = c["id"]
        log("Updated a course", f["title_en"] or f["title_ku"])
    else:
        cur = con.execute(f"INSERT INTO courses ({', '.join(COURSE_FIELDS)}, deadline, questions, accepting, published, slug, "
                          "university_id, created_at, updated_at) VALUES (" + ", ".join("?" * (len(COURSE_FIELDS) + 8)) + ")",
                          values + [u["id"], dbm.now(), dbm.now()])
        cid = cur.lastrowid
        log("Created a course", f["title_en"] or f["title_ku"])
    con.commit()
    flash("Saved.", "ok")
    return redirect(url_for("course_edit", course_id=cid))


@app.post("/admin/courses/<int:course_id>/delete")
@login_required
def course_delete(course_id):
    con = get_db()
    c = target_course(con, course_id)
    con.execute("DELETE FROM submissions WHERE form = ?", (f"course:{c['id']}",))
    con.execute("DELETE FROM courses WHERE id = ?", (c["id"],))
    log("Deleted a course", c["title_en"] or c["title_ku"])
    con.commit()
    flash("Course and its applications deleted.", "ok")
    return redirect(url_for("uni_courses", uni_id=c["university_id"]))


def csv_safe(cell):
    return "'" + cell if cell[:1] in "=+-@" else cell


def answer_rows(c, fields):
    """[(label, value, kind)] for one course application, in the order of the form."""
    rows = [("Full name", fields.get("full_name", ""), "text"), ("Email", fields.get("email", ""), "text"),
            ("Phone or WhatsApp", fields.get("phone", ""), "text")]
    for q in course_questions(c):
        rows.append((q_text(q, "label", "en"), fields.get(q["id"], ""), "availability" if q["type"] == "availability" else "text"))
    rows.append(("Form language", fields.get("language", "English"), "text"))
    return rows


@app.get("/admin/courses/<int:course_id>/applications")
@login_required
def course_applications(course_id):
    con = get_db()
    c = target_course(con, course_id)
    u = target_uni(con, c["university_id"])
    rows = con.execute("SELECT * FROM submissions WHERE form = ? ORDER BY id DESC", (f"course:{c['id']}",)).fetchall()
    avail = None
    if any(q["type"] == "availability" for q in course_questions(c)):
        lists = [dbm.submission_fields(r).get("availability", "") for r in rows]
        if any(lists):
            avail = availability_table([v for v in lists if v])
    return render_template("admin/course_applications.html", u=u, c=c, rows=rows, avail=avail,
                           active="universities" if is_staff(current_user()) else "uni_courses")


@app.get("/admin/course-applications/<int:sub_id>")
@login_required
def course_application(sub_id):
    con = get_db()
    row = con.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    m = re.fullmatch(r"course:(\d+)", row["form"]) if row else None
    if not m:
        abort(404)
    c = target_course(con, int(m.group(1)))
    u = target_uni(con, c["university_id"])
    fields = dbm.submission_fields(row)
    answers = []
    for label, value, kind in answer_rows(c, fields):
        answers.append({"label": label, "value": value,
                        "grid": availability_table([value]) if kind == "availability" and value else None})
    return render_template("admin/course_application.html", u=u, c=c, row=row, answers=answers,
                           active="universities" if is_staff(current_user()) else "uni_courses")


@app.post("/admin/course-applications/<int:sub_id>/delete")
@login_required
def course_application_delete(sub_id):
    con = get_db()
    row = con.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    m = re.fullmatch(r"course:(\d+)", row["form"]) if row else None
    if not m:
        abort(404)
    c = target_course(con, int(m.group(1)))
    con.execute("DELETE FROM submissions WHERE id = ?", (sub_id,))
    log("Deleted a course application", f"{c['title_en'] or c['title_ku']}: {row['name']}")
    con.commit()
    flash("Deleted.", "ok")
    return redirect(url_for("course_applications", course_id=c["id"]))


@app.get("/admin/courses/<int:course_id>/applications.csv")
@login_required
def course_applications_csv(course_id):
    con = get_db()
    c = target_course(con, course_id)
    rows = con.execute("SELECT * FROM submissions WHERE form = ? ORDER BY id", (f"course:{c['id']}",)).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    header = None
    for r in rows:
        answers = answer_rows(c, dbm.submission_fields(r))
        if header is None:
            header = ["Received (UTC)"] + [a[0] for a in answers]
            w.writerow(header)
        w.writerow([r["created_at"]] + [csv_safe(str(a[1])) for a in answers])
    if header is None:
        w.writerow(["Received (UTC)"] + [a[0] for a in answer_rows(c, {})])
    log("Downloaded course applications", c["title_en"] or c["title_ku"])
    con.commit()
    name = (c["slug"] or "course") + "-applications.csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")),
            debug=os.environ.get("KAISH_DEBUG", "0") == "1")
