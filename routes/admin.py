# Admin panel — session auth, roles (superadmin / admin), CRUD for all content.

import io
import json
import os
import uuid
import zipfile
from datetime import date
from functools import wraps

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, send_file, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from data.store import DATA_DIR, UPLOADS_DIR, load, save

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _save_uploaded_image():
    """If an image file was uploaded, save it and return its URL (else None)."""
    file = request.files.get("image_file")
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        flash("Unsupported image type.", "error")
        return None
    fname = uuid.uuid4().hex[:8] + "_" + secure_filename(file.filename)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    file.save(os.path.join(UPLOADS_DIR, fname))
    return "/uploads/" + fname

admin_bp = Blueprint("admin", __name__)


@admin_bp.errorhandler(OSError)
def save_failed(e):
    # Make failed writes VISIBLE (e.g. read-only filesystem on some hosts)
    flash(f"SAVE FAILED — your change was NOT stored: {e}. "
          "Check that AIKURD_DATA_DIR points to a writable, persistent disk.",
          "error")
    return redirect(url_for("admin.dashboard"))

# Every editable collection: label + fields (fields ending in _ku and
# 'text' are rendered RTL in the dashboard).
COLLECTIONS = {
    "tools": {"label": "AI Tools",
              "fields": ["name", "category", "desc_en", "desc_ku", "url"]},
    "prompts": {"label": "Prompts",
                "fields": ["title", "category", "text", "image"]},
    "articles": {"label": "Articles",
                 "fields": ["title_en", "title_ku", "type", "lang", "date",
                             "desc_en", "body_en", "body_ku", "image", "slug"]},
    "tutorials": {"label": "Tutorials",
                  "fields": ["title_en", "title_ku", "desc_en", "level"]},
    "projects": {"label": "Our Projects",
                 "fields": ["name", "category", "desc", "url", "image"]},
    "boosts": {"label": "Daily Boost Messages",
               "fields": ["text_en", "text_ku"]},
    "moods": {"label": "Mood Responses",
              "fields": ["mood", "emoji", "label_en", "label_ku",
                          "response_en", "response_ku", "action_en", "action_ku"]},
}

SETTINGS_FIELDS = ["hero_en_1", "hero_en_2", "hero_ku_1", "hero_ku_2", "sub_en", "sub_ku"]
FEATURED_FIELDS = ["name", "category", "tagline_en", "tagline_ku", "url", "badge"]


# ---------- auth helpers ----------

def current_user():
    username = session.get("user")
    if not username:
        return None
    return next((u for u in load("users") if u["username"] == username), None)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return wrapper


def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.get("role") != "superadmin":
            abort(403)
        return f(*args, **kwargs)
    return wrapper


# ---------- auth routes ----------

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = next((u for u in load("users") if u["username"] == username), None)
        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            return redirect(url_for("admin.dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("admin/login.html", active_page=None)


@admin_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("main.home"))


# ---------- dashboard ----------

@admin_bp.route("/")
@login_required
def dashboard():
    return render_template(
        "admin/dashboard.html",
        active_page="admin",
        collections=COLLECTIONS,
        data={name: load(name) for name in COLLECTIONS},
        settings=load("settings", {}),
        users=load("users"),
        me=current_user(),
    )


# ---------- site settings ----------

@admin_bp.route("/settings", methods=["POST"])
@login_required
def save_settings():
    settings = load("settings", {})
    for key in SETTINGS_FIELDS:
        settings[key] = request.form.get(key, settings.get(key, ""))
    featured = settings.setdefault("featured", {})
    for key in FEATURED_FIELDS:
        featured[key] = request.form.get("featured_" + key, featured.get(key, ""))
    save("settings", settings)
    flash("Site settings saved.", "ok")
    return redirect(url_for("admin.dashboard"))


# ---------- generic collection CRUD ----------

def _collection_or_404(name):
    if name not in COLLECTIONS:
        abort(404)
    return load(name)


def _slugify(text):
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "article"


def _ensure_slug(item, items, current_idx=None):
    """Articles need a unique slug — generate from the title if empty."""
    slug = item.get("slug", "").strip() or _slugify(item.get("title_en", ""))
    taken = {x.get("slug") for i, x in enumerate(items) if i != current_idx}
    base, n = slug, 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    item["slug"] = slug


@admin_bp.route("/<coll>/add", methods=["POST"])
@login_required
def add_item(coll):
    items = _collection_or_404(coll)
    item = {f: request.form.get(f, "").strip() for f in COLLECTIONS[coll]["fields"]}
    if "image" in COLLECTIONS[coll]["fields"]:
        uploaded = _save_uploaded_image()
        if uploaded:
            item["image"] = uploaded
    if "slug" in COLLECTIONS[coll]["fields"]:
        _ensure_slug(item, items)
    items.append(item)
    save(coll, items)
    flash(f"Added to {COLLECTIONS[coll]['label']}.", "ok")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/<coll>/<int:idx>/edit", methods=["POST"])
@login_required
def edit_item(coll, idx):
    items = _collection_or_404(coll)
    if not 0 <= idx < len(items):
        abort(404)
    for f in COLLECTIONS[coll]["fields"]:
        items[idx][f] = request.form.get(f, items[idx].get(f, "")).strip()
    if "image" in COLLECTIONS[coll]["fields"]:
        uploaded = _save_uploaded_image()
        if uploaded:
            items[idx]["image"] = uploaded
    if "slug" in COLLECTIONS[coll]["fields"]:
        _ensure_slug(items[idx], items, current_idx=idx)
    save(coll, items)
    flash("Saved.", "ok")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/<coll>/<int:idx>/delete", methods=["POST"])
@login_required
def delete_item(coll, idx):
    items = _collection_or_404(coll)
    if not 0 <= idx < len(items):
        abort(404)
    items.pop(idx)
    save(coll, items)
    flash("Deleted.", "ok")
    return redirect(url_for("admin.dashboard"))


# ---------- user management (superadmin only) ----------

@admin_bp.route("/users/add", methods=["POST"])
@superadmin_required
def add_user():
    users = load("users")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "admin")
    if role not in ("admin", "superadmin"):
        role = "admin"
    if not username or len(password) < 6:
        flash("Username required; password must be at least 6 characters.", "error")
    elif any(u["username"] == username for u in users):
        flash("That username already exists.", "error")
    else:
        users.append({"username": username,
                      "password": generate_password_hash(password),
                      "role": role})
        save("users", users)
        flash(f"Admin '{username}' created.", "ok")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/users/<username>/delete", methods=["POST"])
@superadmin_required
def delete_user(username):
    me = current_user()
    if username == me["username"]:
        flash("You can't delete yourself.", "error")
    else:
        users = [u for u in load("users") if u["username"] != username]
        save("users", users)
        flash(f"Admin '{username}' removed.", "ok")
    return redirect(url_for("admin.dashboard"))


# ---------- backup (download all data + uploaded images) ----------

@admin_bp.route("/backup")
@login_required
def backup():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(DATA_DIR):
            if fname.endswith(".json"):
                zf.write(os.path.join(DATA_DIR, fname), "data/" + fname)
        if os.path.isdir(UPLOADS_DIR):
            for fname in os.listdir(UPLOADS_DIR):
                zf.write(os.path.join(UPLOADS_DIR, fname), "uploads/" + fname)
    buf.seek(0)
    return send_file(buf, as_attachment=True, mimetype="application/zip",
                     download_name=f"aikurd-backup-{date.today()}.zip")


# ---------- change own password ----------

@admin_bp.route("/password", methods=["POST"])
@login_required
def change_password():
    new = request.form.get("new_password", "")
    if len(new) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(url_for("admin.dashboard"))
    users = load("users")
    me = session["user"]
    for u in users:
        if u["username"] == me:
            u["password"] = generate_password_hash(new)
    save("users", users)
    flash("Password changed.", "ok")
    return redirect(url_for("admin.dashboard"))
