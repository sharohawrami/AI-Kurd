"""Page renderer shared by the web app (app.py) and the static export (build.py).

Every visible text on every page is identified by a stable key (a hash of the original
wording and where it lives). Admins can override any of them; the override is applied
here at render time, so the page templates in src/pages stay the source of truth.

Scopes:
  "<page>"  text inside one page's content (e.g. "index", "program", "join-us-apply")
  "layout"  the shared header, footer, mailing-list block and news-card labels
"""
import datetime
import hashlib
import html
import json
import pathlib
import re

import ornaments as orn

ROOT = pathlib.Path(__file__).resolve().parent
PAGES = ROOT / "src" / "pages"

TOKEN = re.compile(r"\{\{\s*([a-z0-9_:]+)\s*\}\}")
TAG_SPLIT = re.compile(r"(<[^>]*>)")
TAG_NAME = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9-]*)")
ATTR_RE = re.compile(r'(\s(placeholder|aria-label|title|alt|data-ineligible)=")([^"]*)(")')
LETTER = re.compile(r"[^\W\d_]")
RAW_TEXT_TAGS = ("script", "style", "svg", "textarea")
NO_WRAP_TAGS = ("option", "title")
SPECIAL = ("attention_svg", "mark_svg", "kilim", "spandrels")

UI = {
    "en": {
        "html_lang": "en", "dir": "ltr", "base": "",
        "nav": [("program", "Program", "courses/12-week-program.html"),
                ("resources", "Reading library", "resources.html"),
                ("news", "News", "news.html"),
                ("universities", "Universities", "universities.html"),
                ("about", "About", "about.html"),
                ("join", "Join us", "join-us.html")],
        "nav_label": "Main",
        "skip": "Skip to content",
        "apply": "Apply for Cohort 1",
        "switch": '<a class="lang-switch" href="{href}" lang="ckb" hreflang="ckb">کوردی</a>',
        "notice": "Applications for Cohort 1 of the {{program_name}} close {{apply_deadline}}, 23:59 Erbil time.",
        "notice_link": "Apply",
        "apply_closed": "Next cohort: notify me",
        "notice_closed": "Applications for Cohort 1 are closed. Leave your email and we’ll tell you when the next cohort opens.",
        "notice_link_closed": "Notify me",
        "f_apply_closed": "Next cohort: notify me",
        "brand_en": "Kurdistan AI Safety Hub",
        "gb_name": "Kurdistan AI Safety Hub",
        "nl_title": "Stay in touch",
        "nl_body": "Occasional emails about application rounds, reading groups and public talks. A few messages a term. We never share your address.",
        "nl_label": "Email address",
        "nl_button": "Subscribe",
        "nl_hp": "Website",
        "tagline": "Building AI safety research capacity in the Kurdistan Region.",
        "f_program": "Program", "f_syllabus": "The 12 weeks", "f_apply": "Apply",
        "f_learn": "Learn", "f_library": "Reading library", "f_syllabi": "Open syllabi", "f_paths": "Study paths",
        "f_hub": "Hub", "f_news": "News and events", "f_universities": "Universities", "f_about": "About", "f_join": "Join our team", "f_contact": "Contact:",
        "affiliation": "An academic initiative affiliated with AI Kurd.",
        "copyright": "© 2026 Kurdistan AI Safety Hub",
        "privacy": "Privacy",
        "k_news": "News", "k_event": "Event", "read_more": "Read more", "draft": "Draft: only admins can see this post.",
        "acct_label": "Your account", "signin": "Sign in", "register": "Register", "my_profile": "My profile",
        "theme_label": "Dark mode", "theme_title": "Switch between light and dark",
        "months": ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"],
    },
    "ku": {
        "html_lang": "ckb", "dir": "rtl", "base": "ku/",
        "nav": [("program", "پرۆگرام", "courses/12-week-program.html"),
                ("resources", "کتێبخانەی خوێندنەوە", "resources.html"),
                ("news", "هەواڵ", "news.html"),
                ("universities", "زانکۆکان", "universities.html"),
                ("about", "دەربارە", "about.html"),
                ("join", "کار لەگەڵمان", "join-us.html")],
        "nav_label": "سەرەکی",
        "skip": "بڕۆ بۆ ناوەڕۆک",
        "apply": "داواکاری بۆ خولی یەکەم",
        "switch": '<a class="lang-switch" href="{href}" lang="en" hreflang="en">English</a>',
        "notice": "دوا وادەی پێشکەشکردنی داواکاری بۆ خولی یەکەمی {{program_name}}: {{apply_deadline}}، کاتژمێر ٢٣:٥٩ بە کاتی هەولێر.",
        "notice_link": "داواکاری پێشکەش بکە",
        "apply_closed": "خولی داهاتوو: ئاگادارم بکەرەوە",
        "notice_closed": "وەرگرتنی داواکاری بۆ خولی یەکەم داخراوە. ئیمەیڵەکەت بهێڵەوە، کاتێک خولی داهاتوو دەکرێتەوە ئاگادارت دەکەینەوە.",
        "notice_link_closed": "ئاگادارم بکەرەوە",
        "f_apply_closed": "خولی داهاتوو: ئاگادارم بکەرەوە",
        "brand_en": "Kurdistan AI Safety Hub",
        "gb_name": "ناوەندی کوردستان بۆ سەلامەتیی زیرەکیی دەستکرد",
        "nl_title": "پەیوەندیمان لەگەڵ بهێڵەوە",
        "nl_body": "جارجار ئیمەیڵێکت بۆ دەنێرین دەربارەی کاتی پێشکەشکردنی داواکاری، گروپەکانی خوێندنەوە و وتارە گشتییەکان. لە هەر وەرزێکدا چەند نامەیەک. ناونیشانەکەت لەگەڵ کەس بەش ناکەین.",
        "nl_label": "ناونیشانی ئیمەیڵ",
        "nl_button": "بەشداربوون",
        "nl_hp": "ماڵپەڕ",
        "tagline": "بنیاتنانی توانای توێژینەوە لە سەلامەتیی زیرەکیی دەستکرد لە هەرێمی کوردستان.",
        "f_program": "پرۆگرام", "f_syllabus": "١٢ هەفتەکە", "f_apply": "پێشکەشکردن",
        "f_learn": "فێربوون", "f_library": "کتێبخانەی خوێندنەوە", "f_syllabi": "پلانە کراوەکانی خوێندن", "f_paths": "ڕێچکەکانی خوێندن",
        "f_hub": "ناوەند", "f_news": "هەواڵ و چالاکییەکان", "f_universities": "زانکۆکان", "f_about": "دەربارە", "f_join": "پەیوەندی بە تیمەکەمانەوە بکە", "f_contact": "پەیوەندی:",
        "affiliation": "دەستپێشخەرییەکی ئەکادیمییە و پەیوەستە بە AI Kurd.",
        "copyright": "© ٢٠٢٦ ناوەندی کوردستان بۆ سەلامەتیی زیرەکیی دەستکرد",
        "privacy": "تایبەتمەندی",
        "k_news": "هەواڵ", "k_event": "چالاکی", "read_more": "زیاتر بخوێنەوە", "draft": "ڕەشنووس: تەنها بەڕێوەبەران ئەم بابەتە دەبینن.",
        "acct_label": "هەژمارەکەت", "signin": "چوونەژوورەوە", "register": "خۆتۆمارکردن", "my_profile": "پرۆفایلەکەم",
        "theme_label": "دۆخی تاریک", "theme_title": "گۆڕین لە نێوان ڕووناک و تاریک",
        "months": ["کانوونی دووەم", "شوبات", "ئازار", "نیسان", "ئایار", "حوزەیران", "تەممووز", "ئاب",
                   "ئەیلوول", "تشرینی یەکەم", "تشرینی دووەم", "کانوونی یەکەم"],
    },
}

KU_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# Weekly availability table on the cohort application: Saturday to Friday, 08:00 to 23:00 Erbil time.
AVAIL_DAYS = [("Sat", "Saturday", "شەممە"), ("Sun", "Sunday", "یەکشەممە"), ("Mon", "Monday", "دووشەممە"),
              ("Tue", "Tuesday", "سێشەممە"), ("Wed", "Wednesday", "چوارشەممە"), ("Thu", "Thursday", "پێنجشەممە"),
              ("Fri", "Friday", "هەینی")]
AVAIL_HOURS = list(range(8, 23))   # each row is one hour: 08:00–09:00 … 22:00–23:00


LAYOUT_LABELS = {"notice": "Announcement bar at the very top", "account": "Sign in and Register buttons",
                 "apply-button": "Apply button in the menu", "newsletter": "Stay in touch (mailing list sign-up)",
                 "footer-program": "Footer: Program column", "footer-learn": "Footer: Learn column",
                 "footer-hub": "Footer: Hub column", "footer-contact": "Footer: contact email",
                 "footer-affiliation": "Footer: AI Kurd affiliation line"}
NAV_PAGES = {"program": "program", "resources": "resources", "news": "news", "about": "about", "join": "join-us",
             "universities": "universities"}
WHEN_TAG = re.compile(r'<([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*\bdata-when="(open|closed)"[^>]*>')
SEC_TAG = re.compile(r'<([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*\bdata-(sec|page)="([^"]+)"[^>]*>')
ANY_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*?(/?)>")


def element_end(html_text, start, name):
    """Index just past the closing tag of the element whose start tag begins at `start`."""
    depth = 0
    name = name.lower()
    for m in ANY_TAG.finditer(html_text, start):
        if m.group(2).lower() != name or m.group(3):
            continue
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.end()
    return len(html_text)


def section_label(fragment):
    for pat in (r'<p class="sec-label"[^>]*>(.*?)</p>', r"<h1[^>]*>(.*?)</h1>", r"<h2[^>]*>(.*?)</h2>",
                r"<h3[^>]*>(.*?)</h3>", r"<h4[^>]*>(.*?)</h4>", r'<p class="label"[^>]*>(.*?)</p>'):
        m = re.search(pat, fragment, re.S)
        if m:
            text = norm(html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))))
            if text:
                return text
    return norm(html.unescape(re.sub(r"<[^>]+>", " ", fragment)))[:70]


def list_sections(html_text):
    """[(key, label)] for every hideable block, first occurrence of each key, in page order."""
    out, seen = [], set()
    for m in SEC_TAG.finditer(html_text):
        tag = m.group(0)
        km = re.search(r'data-sec="([^"]+)"', tag)
        if not km:
            continue
        key = km.group(1)
        if key in seen:
            continue
        seen.add(key)
        frag = html_text[m.end(): element_end(html_text, m.start(), m.group(1))]
        out.append((key, LAYOUT_LABELS.get(key) or section_label(frag)))
    return out


def availability_grid(lang):
    ku = lang == "ku"
    loc = (lambda t: t.translate(KU_DIGITS)) if ku else (lambda t: t)
    hour = lambda h: loc(f"{h:02d}:00")
    head = "".join(
        f'<th scope="col"><button type="button" class="avail-day" data-col="{c}" '
        f'aria-label="{(ku_name + "، هەموو کاتژمێرەکان") if ku else (full + ", every hour")}">'
        f'{ku_name if ku else short}</button></th>'
        for c, (short, full, ku_name) in enumerate(AVAIL_DAYS))
    rows = []
    for r, h in enumerate(AVAIL_HOURS):
        span = f"{hour(h)}–{hour(h + 1)}"
        cells = "".join(
            f'<td><label class="avail-cell" for="av-{c}-{r}" title="{(ku_name if ku else full)} {span}">'
            f'<input type="checkbox" id="av-{c}-{r}" name="availability" value="{short} {h:02d}:00" data-col="{c}" data-row="{r}">'
            f'<span class="sq" aria-hidden="true"></span><span class="sr">{(ku_name if ku else full)} {span}</span></label></td>'
            for c, (short, full, ku_name) in enumerate(AVAIL_DAYS))
        label = f"{span}، هەموو ڕۆژەکان" if ku else f"{span}, every day"
        rows.append(f'<tr><th scope="row"><button type="button" class="avail-hour" data-row="{r}" aria-label="{label}">'
                    f'{hour(h)}</button></th>{cells}</tr>')
    corner = "کاتژمێر" if ku else "Hour"
    return (f'<div class="avail" data-avail><div class="avail-wrap"><table class="avail-grid">'
            f'<thead><tr><th scope="col"><span class="sr">{corner}</span></th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<p class="avail-count" aria-live="polite"></p></div>')
# Applies a visitor's saved light/dark choice before the page is drawn, so it never flashes.
THEME_SCRIPT = ('<script>try{var t=localStorage.getItem("kaish-theme");'
                'if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}</script>')


def load_site():
    return json.loads((ROOT / "site.json").read_text(encoding="utf-8"))


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def text_key(scope, text):
    return hashlib.sha1(f"{scope}\n{text}".encode("utf-8")).hexdigest()[:12]


def value_only(text):
    """True when a text is nothing but {{tokens}}, numbers and punctuation."""
    return not LETTER.search(TOKEN.sub("", text))


def parse(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"\s*<!--(.*?)-->", raw, re.S)
    meta = {}
    for line in m.group(1).strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, raw[m.end():]


def page_sources():
    """[(lang, name, meta, body)] for every page template, English first."""
    out = []
    for lang, folder in (("en", PAGES), ("ku", PAGES / "ku")):
        for path in sorted(folder.glob("*.html")):
            meta, body = parse(path)
            out.append((lang, path.stem, meta, body))
    return out


def out_path(lang, meta):
    return UI[lang]["base"] + meta["out"]


_PAGE_BY_OUT = {}


def page_for_href(href):
    """The page (template name) a relative link points to, or None for other links."""
    if not _PAGE_BY_OUT:
        for _lang, name, meta, _body in page_sources():
            if not meta.get("dynamic") and name != "news-post":
                _PAGE_BY_OUT[meta["out"]] = name
    h = href.split("#")[0].split("?")[0]
    if re.match(r"^[a-z][a-z0-9+.-]*:", h, re.I):
        return None
    while h.startswith("../"):
        h = h[3:]
    h = h.lstrip("/")
    if h.startswith("ku/"):
        h = h[3:]
    if h == "universities" or h.startswith(("universities.html", "universities/")):
        return "universities"
    if h.startswith("news/"):
        return "news"
    if h and not h.endswith(".html"):
        h += ".html"
    return _PAGE_BY_OUT.get(h)


def fmt_date(iso, lang):
    if not iso:
        return ""
    try:
        d = datetime.date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    month = UI[lang]["months"][d.month - 1]
    if lang == "ku":
        return f"{d.day}ی {month} {d.year}".translate(KU_DIGITS)
    return f"{d.day} {month} {d.year}"


def paragraphs(text):
    text = (text or "").strip()
    if not text:
        return ""
    parts = re.split(r"\n\s*\n", text)
    return "".join("<p>" + html.escape(p.strip()).replace("\n", "<br>") + "</p>" for p in parts if p.strip())


def braces(s):
    """Stop text typed by admins from being read as a {{token}} later in the render."""
    return s.replace("{", "&#123;")


def post_field(post, field, lang):
    """A post's field in this language, falling back to the other language."""
    v = (post.get(f"{field}_{lang}") or "").strip()
    if v:
        return v, lang
    other = "ku" if lang == "en" else "en"
    return (post.get(f"{field}_{other}") or "").strip(), other


class Renderer:
    def __init__(self, values=None, labels=None, texts=None, posts=None, endpoint="",
                 edit=False, collect=False, pretty_urls=False, accounts=False, hidden=None):
        site = load_site()
        self.values = dict(site["values"])
        self.values.update(values or {})
        self.labels = {"en": site["labels"], "ku": site.get("labels_ku", {})}
        if labels:
            self.labels.update(labels)
        self.texts = texts or {}          # {(lang, scope, key): value}
        self.posts = posts or []          # published posts, newest first
        self.endpoint = endpoint
        self.edit = edit
        self.collecting = collect
        self.items = []                   # collected editable texts
        self._seen = set()
        self.lang = "en"
        self.raw = {}                     # raw HTML tokens for this render
        self.accounts = accounts          # show Sign in / Register (only when served by app.py)
        self.hidden = set(hidden or ())   # {(scope, key)}: sections hidden by admins; ("page", name) for pages
        self.set_member(None)

    def set_member(self, member, avatar_html=""):
        """Header state: signed out (Sign in, Register) or signed in (picture and first name)."""
        hide = (" hidden", " hidden")
        if member:
            first = (member["full_name"].split() or [""])[0]
            self.raw.update({"acct_out": hide, "acct_in": ("", ""), "acct_avatar": (avatar_html, None),
                             "acct_name": (html.escape(first), first)})
        else:
            self.raw.update({"acct_out": ("", ""), "acct_in": hide, "acct_avatar": ("", None), "acct_name": ("", "")})

    # ---------- values and tokens ----------
    def value(self, key):
        v = self.values.get(key, "")
        return v.strip() if isinstance(v, str) else str(v)

    def localized(self, key):
        if self.lang == "ku":
            v = self.value(key + "_ku")
            if v:
                return v
        return self.value(key)

    def plate_html(self):
        """Plate I on the homepage: the uploaded picture if there is one, otherwise the woven pattern."""
        pic = self.value("hero_image")
        if re.fullmatch(r"[a-f0-9]{24}\.(webp|jpg|png)", pic):
            alt = html.escape(self.localized("hero_image_alt"), quote=True)
            return f'<img class="plate-img" src="{getattr(self, "prefix", "")}uploads/{pic}" alt="{alt}">'
        return orn.attention_svg()

    def render_token(self, raw, in_tag):
        if raw == "attention_svg":
            return self.plate_html()
        if raw in SPECIAL:
            return {"attention_svg": orn.attention_svg, "mark_svg": orn.mark_svg, "kilim": orn.kilim_band,
                    "spandrels": orn.spandrels}[raw]()
        if raw in self.raw:
            html_value, plain = self.raw[raw]
            if in_tag and plain is not None:
                return html.escape(plain, quote=True)
            if self.edit and plain and not in_tag:
                # a value inside an editable sentence stays a chip, so saving the sentence keeps the {{token}}
                return f'<span class="tok" data-tok="{html.escape(raw)}" contenteditable="false">{html_value}</span>'
            return html_value
        kind, _, key = raw.rpartition(":")
        v = self.localized(key)
        label = self.labels[self.lang].get(key) or self.labels["en"].get(key, key.replace("_", " "))
        if not v and kind == "opt":
            return ""
        if in_tag:
            return html.escape(v if v else f"[{label}]", quote=True)
        if not v:
            out = (f'<span class="ph" title="Placeholder: set {key} in Settings">'
                   f"[{html.escape(label)}]</span>")
        elif kind == "mail":
            e = html.escape(v, quote=True)
            out = f'<a href="mailto:{e}" dir="ltr">{e}</a>'
        elif kind == "url":
            e = html.escape(v, quote=True)
            shown = re.sub(r"^https?://(www\.)?", "", v).rstrip("/")
            out = f'<a href="{e}" rel="noopener" dir="ltr">{html.escape(shown)}</a>'
        else:
            out = html.escape(v)
        if self.edit:
            out = f'<span class="tok" data-tok="{html.escape(raw)}" contenteditable="false">{out}</span>'
        return out

    def fill(self, text):
        out = []
        for part in TAG_SPLIT.split(text):
            in_tag = part.startswith("<")
            out.append(TOKEN.sub(lambda m: self.render_token(m.group(1), in_tag), part))
        return "".join(out)

    def fill_plain(self, text):
        return TOKEN.sub(lambda m: self.render_token(m.group(1), True), text)

    # ---------- editable texts ----------
    def record(self, scope, key, text, kind):
        if not self.collecting or (scope, key) in self._seen:
            return
        self._seen.add((scope, key))
        self.items.append({"scope": scope, "key": key, "text": text, "kind": kind,
                           "value": self.texts.get((self.lang, scope, key))})

    def override(self, scope, key):
        return self.texts.get((self.lang, scope, key))

    def process_attrs(self, tag, scope):
        def repl(m):
            name, raw_value = m.group(2), m.group(3)
            core = norm(html.unescape(raw_value))
            if not core or value_only(core):
                return m.group(0)
            key = text_key(scope, f"@{name} {core}")
            self.record(scope, key, core, f"attr:{name}")
            v = self.override(scope, key)
            return m.group(1) + (html.escape(v, quote=True) if v is not None else raw_value) + m.group(4)
        return ATTR_RE.sub(repl, tag)

    def process_texts(self, template, scope):
        out, skip = [], None
        for part in TAG_SPLIT.split(template):
            if part.startswith("<"):
                m = TAG_NAME.match(part)
                if m:
                    closing, name = m.group(1) == "/", m.group(2).lower()
                    if skip is None and not closing and name in RAW_TEXT_TAGS + NO_WRAP_TAGS and not part.rstrip().endswith("/>"):
                        skip = name
                    elif closing and name == skip:
                        skip = None
                    if skip not in ("script", "style", "svg"):
                        part = self.process_attrs(part, scope)
                out.append(part)
                continue
            if skip in RAW_TEXT_TAGS or not part.strip():
                out.append(part)
                continue
            core = norm(html.unescape(part))
            if value_only(core):
                out.append(part)
                continue
            key = text_key(scope, core)
            self.record(scope, key, core, "option" if skip == "option" else ("title" if skip == "title" else "text"))
            v = self.override(scope, key)
            lead = part[: len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()):]
            body = html.escape(v, quote=False) if v is not None else part.strip()
            if self.edit and skip is None:
                body = f'<span class="t-edit" data-t="{scope}|{key}">{body}</span>'
            out.append(lead + body + trail)
        return "".join(out)

    def meta_text(self, scope, field, template):
        core = norm(template)
        key = text_key(scope, f"meta:{field} {core}")
        self.record(scope, key, core, f"meta:{field}")
        v = self.override(scope, key)
        return v if v is not None else template

    # ---------- layout ----------
    def head_html(self, meta, prefix, scope, out, alt_out):
        title = html.escape(self.fill_plain(self.meta_text(scope, "title", meta["title"])))
        desc = html.escape(self.fill_plain(self.meta_text(scope, "description", meta["description"])), quote=True)
        domain = self.value("domain").rstrip("/")
        links = ""
        if domain:
            def url(path):
                return f"{html.escape(domain)}/{path.replace('index.html', '')}"
            en_out, ku_out = (out, alt_out) if self.lang == "en" else (alt_out, out)
            links = (f'<link rel="canonical" href="{url(out)}">\n'
                     f'<link rel="alternate" hreflang="en" href="{url(en_out)}">\n'
                     f'<link rel="alternate" hreflang="ckb" href="{url(ku_out)}">\n')
        # member pages are private; public pages that app.py fills in (universities) are marked "index: yes"
        robots = '<meta name="robots" content="noindex">\n' if meta.get("dynamic") and meta.get("index") != "yes" else ""
        return f"""<title>{title}</title>
{robots}<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:locale" content="{'ckb_IQ' if self.lang == 'ku' else 'en_US'}">
<meta name="kaish-endpoint" content="{html.escape(self.endpoint, quote=True)}">
{links}{THEME_SCRIPT}
<link rel="icon" href="{prefix}favicon.ico" sizes="48x48">
<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{prefix}assets/apple-touch-icon.png">
<link rel="manifest" href="{prefix}assets/site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&amp;family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&amp;family=IM+Fell+English:ital@0;1&amp;family=IM+Fell+English+SC&amp;display=swap">
<link rel="stylesheet" href="{prefix}assets/site.css">"""

    def header_template(self, active, prefix, switch_href):
        ui = UI[self.lang]
        base = prefix + ui["base"]
        links = []
        for key, label, href in ui["nav"]:
            cur = ' aria-current="page"' if key == active else ""
            links.append(f'<a href="{base}{href}" data-page="{NAV_PAGES.get(key, key)}"{cur}>{label}</a>')
        switch = ui["switch"].format(href=switch_href)
        theme = (f'<button type="button" class="theme-switch" data-theme-toggle aria-pressed="false" '
                 f'aria-label="{ui["theme_label"]}" title="{ui["theme_title"]}" hidden>'
                 f'<span class="ts-sun">{orn.sun_svg()}</span><span class="ts-moon">{orn.moon_svg()}</span></button>')
        account = ""
        if self.accounts:
            account = (f'<div class="acct" role="group" aria-label="{ui["acct_label"]}" data-sec="account">'
                       f'<a class="acct-signin" href="{base}signin"{{{{acct_out}}}}>{ui["signin"]}</a>'
                       f'<a class="acct-reg" href="{base}register"{{{{acct_out}}}}>{ui["register"]}</a>'
                       f'<a class="acct-me" href="{base}profile" title="{ui["my_profile"]}"{{{{acct_in}}}}>{{{{acct_avatar}}}}'
                       f'<span class="acct-name">{{{{acct_name}}}}</span></a></div>')
        return f"""<a class="skip" href="#main">{ui["skip"]}</a>
<div class="notice" data-sec="notice" data-page="apply" data-when="open"><div class="wrap notice-in"><p>{ui["notice"]}</p><a href="{base}apply.html">{ui["notice_link"]}</a></div></div>
<div class="notice" data-sec="notice" data-page="apply" data-when="closed"><div class="wrap notice-in"><p>{ui["notice_closed"]}</p><a href="{base}apply.html#notify">{ui["notice_link_closed"]}</a></div></div>
<header class="site-header">
  <div class="kilim-wrap">{orn.kilim_band()}</div>
  <div class="wrap mast">
    <a class="brand" href="{base}index.html">{{{{mark_svg}}}}<span class="brand-text"><span class="brand-ku" lang="ckb" dir="rtl">{{{{opt:name_ku}}}}</span><span class="brand-en" lang="en" dir="ltr">{ui["brand_en"]}</span></span></a>
    {account}
    <div class="navrow">
      <nav class="nav" aria-label="{ui["nav_label"]}">{''.join(links)}</nav>
      <a class="btn btn-sm" href="{base}apply.html" data-sec="apply-button" data-page="apply" data-when="open">{ui["apply"]}</a>
      <a class="btn btn-sm" href="{base}apply.html#notify" data-sec="apply-button" data-page="apply" data-when="closed">{ui["apply_closed"]}</a>
      {switch}
      {theme}
    </div>
  </div>
</header>
<div class="glassbar" id="glassbar" inert>
  <div class="wrap glassbar-in">
    <a class="gb-brand" href="{base}index.html">{orn.mark_svg(30)}<span>{ui["gb_name"]}</span></a>
    <nav class="gb-nav" aria-label="{ui["nav_label"]}">{''.join(links)}</nav>
    <a class="btn btn-sm" href="{base}apply.html" data-sec="apply-button" data-page="apply" data-when="open">{ui["apply"]}</a>
    <a class="btn btn-sm" href="{base}apply.html#notify" data-sec="apply-button" data-page="apply" data-when="closed">{ui["apply_closed"]}</a>
    {switch}
    {theme}
  </div>
</div>"""

    def newsletter_template(self):
        ui = UI[self.lang]
        return f"""<section class="nl" aria-labelledby="nl-title" data-sec="newsletter">
  <div class="wrap nl-in">
    <div class="nl-text">
      <h2 id="nl-title">{ui["nl_title"]}</h2>
      <p>{ui["nl_body"]}</p>
    </div>
    <form class="nl-form" id="newsletter-form" data-form="newsletter" novalidate>
      <div class="nl-row">
        <label class="sr" for="nl-email">{ui["nl_label"]}</label>
        <input id="nl-email" name="email" type="email" autocomplete="email" placeholder="you@example.com" required>
        <button class="btn" type="submit">{ui["nl_button"]}</button>
      </div>
      <div class="hp" aria-hidden="true"><label for="nl-website">{ui["nl_hp"]}</label><input id="nl-website" name="website" tabindex="-1" autocomplete="off"></div>
      <p class="nl-msg" role="status"></p>
    </form>
  </div>
</section>"""

    def footer_template(self, prefix):
        ui = UI[self.lang]
        base = prefix + ui["base"]
        return f"""<div class="kilim-wrap foot-kilim">{{{{kilim}}}}</div>
<footer class="site-footer">
  <div class="wrap foot-grid">
    <div class="foot-brand">
      <a class="brand" href="{base}index.html">{{{{mark_svg}}}}<span class="brand-text"><span class="brand-ku" lang="ckb" dir="rtl">{{{{opt:name_ku}}}}</span><span class="brand-en" lang="en" dir="ltr">{ui["brand_en"]}</span></span></a>
      <p>{ui["tagline"]}</p>
    </div>
    <div data-sec="footer-program" data-page="program">
      <h2 class="foot-h">{ui["f_program"]}</h2>
      <ul>
        <li><a href="{base}courses/12-week-program.html">{{{{program_name}}}}</a></li>
        <li><a href="{base}courses/12-week-program.html#syllabus">{ui["f_syllabus"]}</a></li>
        <li data-page="apply" data-when="open"><a href="{base}apply.html">{ui["f_apply"]}</a></li>
        <li data-page="apply" data-when="closed"><a href="{base}apply.html#notify">{ui["f_apply_closed"]}</a></li>
      </ul>
    </div>
    <div data-sec="footer-learn">
      <h2 class="foot-h">{ui["f_learn"]}</h2>
      <ul>
        <li data-page="resources"><a href="{base}resources.html">{ui["f_library"]}</a></li>
        <li data-page="resources"><a href="{base}resources.html#syllabi">{ui["f_syllabi"]}</a></li>
        <li data-page="resources"><a href="{base}resources.html#paths">{ui["f_paths"]}</a></li>
        <li data-page="universities"><a href="{base}universities.html">{ui["f_universities"]}</a></li>
      </ul>
    </div>
    <div data-sec="footer-hub">
      <h2 class="foot-h">{ui["f_hub"]}</h2>
      <ul>
        <li data-page="news"><a href="{base}news.html">{ui["f_news"]}</a></li>
        <li data-page="about"><a href="{base}about.html">{ui["f_about"]}</a></li>
        <li data-page="join-us"><a href="{base}join-us.html">{ui["f_join"]}</a></li>
        <li data-sec="footer-contact">{ui["f_contact"]} {{{{mail:email_hello}}}}</li>
      </ul>
    </div>
  </div>
  <div class="wrap foot-base">
    <p data-sec="footer-affiliation"><strong>{ui["affiliation"]}</strong></p>
    <p>{ui["copyright"]}<span data-page="privacy"> · <a href="{base}privacy.html">{ui["privacy"]}</a></span></p>
  </div>
</footer>"""

    # ---------- news ----------
    def card_skeleton(self):
        ui = UI[self.lang]
        tpl = f"""<article class="card" data-kind="{{{{card_kind}}}}">
  <a class="card-img" href="{{{{card_href}}}}" tabindex="-1" aria-hidden="true">{{{{card_image}}}}</a>
  <div class="card-body">
    <p class="card-kind"><span class="k-news">{ui["k_news"]}</span><span class="k-event">{ui["k_event"]}</span><span class="card-date">{{{{card_date}}}}</span></p>
    <h3 class="card-title"><a href="{{{{card_href}}}}"{{{{card_dir}}}}>{{{{card_title}}}}</a></h3>
    <p class="card-sum"{{{{card_dir}}}}>{{{{card_summary}}}}</p>
    <a class="more" href="{{{{card_href}}}}">{ui["read_more"]}</a>
  </div>
</article>"""
        return self.process_texts(tpl, "layout")

    def uni_card_skeleton(self):
        return self.process_texts("""<a class="uni-card" href="{{card_href}}">
  <span class="uni-logo">{{card_logo}}</span>
  <span class="uni-text"><b dir="auto">{{card_name}}</b><span class="uni-alt" dir="auto">{{card_alt}}</span><span class="uni-city">{{card_city}}</span></span>
  <span class="uni-meta">Open courses: {{card_count}}</span>
</a>""" if self.lang == "en" else """<a class="uni-card" href="{{card_href}}">
  <span class="uni-logo">{{card_logo}}</span>
  <span class="uni-text"><b dir="auto">{{card_name}}</b><span class="uni-alt" dir="auto">{{card_alt}}</span><span class="uni-city">{{card_city}}</span></span>
  <span class="uni-meta">کۆرسی کراوە: {{card_count}}</span>
</a>""", "universities")

    def course_card_skeleton(self):
        en = self.lang == "en"
        return self.process_texts(f"""<article class="course-card" data-open="{{{{card_open}}}}">
  <div class="course-card-body">
    <p class="card-kind"><span class="c-open">{"Applications open" if en else "وەرگرتنی داواکاری کراوەیە"}</span><span class="c-closed">{"Applications closed" if en else "وەرگرتنی داواکاری داخراوە"}</span></p>
    <h3 class="card-title"><a href="{{{{card_href}}}}" dir="auto">{{{{card_title}}}}</a></h3>
    <p class="card-sum" dir="auto">{{{{card_summary}}}}</p>
    <p class="course-when">{{{{card_facts}}}}</p>
  </div>
  <a class="btn btn-sm c-open" href="{{{{card_href}}}}">{"Read more and apply" if en else "زیاتر بخوێنەوە و داواکاری پێشکەش بکە"}</a>
  <a class="more c-closed" href="{{{{card_href}}}}">{"Read more" if en else "زیاتر بخوێنەوە"}</a>
</article>""", "university")

    def fill_skeleton(self, skeleton, values, tokens=("card_count",)):
        """Put one item's values into a card skeleton. In edit mode, values that sit inside an
        editable sentence stay chips, so saving the sentence keeps the {{token}}."""
        out = skeleton
        for k, v in values.items():
            if self.edit and k in tokens:
                v = f'<span class="tok" data-tok="{k}" contenteditable="false">{v}</span>'
            out = out.replace("{{" + k + "}}", v)
        return out

    def kind_label_skeleton(self):
        ui = UI[self.lang]
        return self.process_texts(
            f'<span class="k-news">{ui["k_news"]}</span><span class="k-event">{ui["k_event"]}</span>', "layout")

    def image_html(self, post, prefix, lang, cls="card-pic"):
        if post.get("image"):
            alt, _ = post_field(post, "image_alt", lang)
            if not alt:
                alt, _ = post_field(post, "title", lang)
            return f'<img class="{cls}" src="{prefix}uploads/{html.escape(post["image"], quote=True)}" alt="{braces(html.escape(alt, quote=True))}" loading="lazy">'
        return f'<span class="loom" aria-hidden="true">{orn.mark_svg(46)}</span>'

    def post_href(self, post, prefix):
        return f"{prefix}{UI[self.lang]['base']}news/{post['slug']}.html"

    def post_date(self, post):
        return fmt_date(post.get("event_date") if post.get("kind") == "event" and post.get("event_date")
                        else post.get("published_at") or post.get("created_at"), self.lang)

    def cards(self, posts, prefix):
        skeleton = self.card_skeleton()
        out = []
        for p in posts:
            title, tl = post_field(p, "title", self.lang)
            summary, _ = post_field(p, "summary", self.lang)
            dir_attr = "" if tl == self.lang else (' lang="en" dir="ltr"' if tl == "en" else ' lang="ckb" dir="rtl"')
            card = skeleton
            for k, v in {
                "card_kind": p.get("kind", "news"),
                "card_href": self.post_href(p, prefix),
                "card_image": self.image_html(p, prefix, self.lang),
                "card_date": html.escape(self.post_date(p)),
                "card_title": braces(html.escape(title)),
                "card_summary": braces(html.escape(summary)),
                "card_dir": dir_attr,
            }.items():
                card = card.replace("{{" + k + "}}", v)
            out.append(card)
        return "".join(out)

    def news_tokens(self, prefix, limit=None):
        posts = self.posts[:limit] if limit else self.posts
        if self.collecting:
            self.card_skeleton()
        if posts:
            grid = f'<div class="news-grid">{self.cards(posts, prefix)}</div>'
            hidden = " hidden"
        else:
            slots = "".join(f'<div class="card slot"><div class="card-img"><span class="loom">{orn.mark_svg(46)}</span></div>'
                            f'<div class="card-body"><span class="bar"></span><span class="bar short"></span></div></div>'
                            for _ in range(3))
            grid = f'<div class="news-grid news-empty" aria-hidden="true">{slots}</div>'
            hidden = ""
        self.raw["news_latest"] = (grid, None)
        self.raw["news_all"] = (grid, None)
        self.raw["news_hidden"] = (hidden, hidden)

    # ---------- hiding sections and pages ----------
    def is_hidden(self, scope, kind, key):
        return (("page", key) in self.hidden) if kind == "page" else ((scope, key) in self.hidden)

    def visible(self, html_text, scope):
        """Remove hidden sections (and links to hidden pages) for visitors; in edit mode, mark them instead."""
        if not self.hidden or self.collecting:
            return html_text
        out, pos = [], 0
        for m in SEC_TAG.finditer(html_text):
            if m.start() < pos:
                continue
            tag = m.group(0)
            attrs = dict(re.findall(r'data-(sec|page)="([^"]+)"', tag))
            off = [k for k, v in attrs.items() if self.is_hidden(scope, k, v)]
            if not off:
                continue
            if self.edit:
                marks = "".join(f" data-{k}-off" for k in off)
                out.append(html_text[pos:m.start()] + tag[:-1] + marks + ">")
                pos = m.end()
            else:
                out.append(html_text[pos:m.start()])
                pos = element_end(html_text, m.start(), m.group(1))
        out.append(html_text[pos:])
        return "".join(out)

    def applications_open(self):
        return self.value("applications_open") == "1"

    def apply_state(self, html_text):
        """Keep the parts written for the current state of Cohort applications (data-when="open" or
        "closed"). Visitors only get the current one; in edit mode the other stays, hidden, so it can be edited."""
        if self.collecting:
            return html_text
        now = "open" if self.applications_open() else "closed"
        out, pos = [], 0
        for m in WHEN_TAG.finditer(html_text):
            if m.start() < pos or m.group(2) == now:
                continue
            if self.edit:
                out.append(html_text[pos:m.start()] + m.group(0)[:-1] + " hidden>")
                pos = m.end()
            else:
                out.append(html_text[pos:m.start()])
                pos = element_end(html_text, m.start(), m.group(1))
        out.append(html_text[pos:])
        return "".join(out)

    def unlink_hidden(self, html_text):
        """For visitors, links inside page text that lead to a hidden page: buttons and "read more"
        links are removed, links inside a sentence become plain text."""
        pages = {k for (sc, k) in self.hidden if sc == "page"}
        if not pages or self.edit or self.collecting:
            return html_text

        def repl(m):
            href = re.search(r'\bhref="([^"]*)"', m.group(1))
            if not href or page_for_href(href.group(1)) not in pages:
                return m.group(0)
            cls = re.search(r'\bclass="([^"]*)"', m.group(1))
            if cls and re.search(r"\b(more|btn)\b", cls.group(1)):
                return ""
            return m.group(2)
        return re.sub(r"<a\b([^>]*)>(.*?)</a>", repl, html_text, flags=re.S)

    # ---------- pages ----------
    def wrap_stitches(self, content):
        return re.sub(r"<h2([^>]*)>(.*?)</h2>", r'<h2\1><span class="stitch">\2</span></h2>', content, flags=re.S)

    def assemble(self, lang, scope, meta, body, out, alt_out, extra_body=""):
        self.lang = lang
        prefix = "../" * out.count("/")
        self.prefix = prefix
        page_root = prefix + UI[lang]["base"]
        depth = out.count("/")
        switch_href = "../" * depth + alt_out
        if "news_" in body:
            self.news_tokens(prefix, limit=3 if scope == "index" else None)
        if "{{availability_grid}}" in body:
            self.raw["availability_grid"] = (availability_grid(lang), None)
        top = self.apply_state(self.visible(self.process_texts(self.header_template(meta.get("nav", ""), prefix, switch_href), "layout"), "layout"))
        content = self.unlink_hidden(self.apply_state(self.visible(self.process_texts(body.replace("{{root}}", page_root), scope), scope)))
        bottom = ""
        if meta.get("newsletter", "yes") != "no":
            bottom += self.process_texts(self.newsletter_template(), "layout")
        bottom += self.process_texts(self.footer_template(prefix), "layout")
        bottom = self.apply_state(self.visible(bottom, "layout"))
        page = (top + f'\n<main id="main">{content}</main>\n' + bottom
                + f'\n<script src="{prefix}assets/site.js" defer></script>')
        page = self.wrap_stitches(self.fill(page))
        head = self.head_html(meta, prefix, scope, out, alt_out)
        return head, page + extra_body

    def render(self, lang, name, full=True, extra_head="", extra_body="", out=None):
        meta, body = self.template(lang, name)
        if out:
            meta = dict(meta, out=out)
        if meta.get("dynamic"):
            # values that app.py fills in per visitor; empty when it doesn't (e.g. while collecting texts)
            for tok in TOKEN.findall(body + meta.get("title", "") + meta.get("description", "")):
                if tok not in self.raw and tok not in SPECIAL and ":" not in tok and tok != "root" and tok not in self.values:
                    self.raw[tok] = ("", "")
        other = "ku" if lang == "en" else "en"
        out, alt_out = out_path(lang, meta), out_path(other, meta)
        head, page = self.assemble(lang, name, meta, body, out, alt_out, extra_body)
        return self.document(head + extra_head, page, full)

    def render_post(self, lang, post, full=True, extra_head="", extra_body="", draft=False):
        meta, body = self.template(lang, "news-post")
        out = f"{UI[lang]['base']}news/{post['slug']}.html"
        other = "ku" if lang == "en" else "en"
        alt_out = f"{UI[other]['base']}news/{post['slug']}.html"
        self.lang = lang
        prefix = "../" * out.count("/")
        title, tl = post_field(post, "title", lang)
        summary, _ = post_field(post, "summary", lang)
        body_text, bl = post_field(post, "body", lang)
        location, _ = post_field(post, "location", lang)
        facts = [self.post_date(post)]
        if post.get("kind") == "event" and post.get("event_time"):
            facts.append(post["event_time"].translate(KU_DIGITS) if lang == "ku" else post["event_time"])
        if location:
            facts.append(location)
        dir_attr = "" if bl == lang else (' lang="en" dir="ltr"' if bl == "en" else ' lang="ckb" dir="rtl"')
        image = ""
        if post.get("image"):
            image = f'<figure class="post-figure">{self.image_html(post, prefix, lang, "post-pic")}</figure>'
        self.raw.update({
            "post_title": (html.escape(title), title),
            "post_summary": (html.escape(summary), summary),
            "post_kind": (html.escape(post.get("kind", "news")), post.get("kind", "news")),
            "post_facts": ("".join(f"<span>{html.escape(f)}</span>" for f in facts if f), None),
            "post_image": (image, None),
            "post_body": (f'<div class="post-text prose-stack"{dir_attr}>{paragraphs(body_text)}</div>', None),
            "post_draft": (f'<p class="note">{html.escape(UI[lang]["draft"])}</p>' if draft else "", None),
        })
        source = post.get("_source")   # (name, href) when a university posted it
        self.raw["post_source"] = ((f'<a href="{prefix}{html.escape(source[1], quote=True)}">{html.escape(source[0])}</a>'
                                    if source else ""), source[0] if source else "")
        self.raw["post_source_hidden"] = ("", "") if source else (" hidden", " hidden")
        head, page = self.assemble(lang, "news-post", meta, body, out, alt_out, extra_body)
        return self.document(head + extra_head, page, full)

    def template(self, lang, name):
        folder = PAGES if lang == "en" else PAGES / "ku"
        return parse(folder / f"{name}.html")

    def document(self, head, page, full):
        ui = UI[self.lang]
        if not full:
            return f"{head}\n{page}\n"
        return (f'<!doctype html>\n<html lang="{ui["html_lang"]}" dir="{ui["dir"]}">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                f"{head}\n</head>\n<body>\n{page}\n</body>\n</html>\n")

    def collect(self, lang, name):
        """All editable texts on one page, in the order they appear."""
        self.collecting, self.items, self._seen = True, [], set()
        if name == "news-post":
            sample = {"slug": "sample", "kind": "news", "title_en": "Sample", "title_ku": "Sample"}
            self.render_post(lang, sample)
            self.kind_label_skeleton()
        else:
            self.render(lang, name)
            if name == "universities":
                self.uni_card_skeleton()
            elif name == "university":
                self.course_card_skeleton()
        return self.items
