"""Static copy of the website, for hosting without the admin panel.

  python build.py

Writes dist/ (upload anywhere) and preview/ (used for the shareable preview). Includes every
text edit, setting and published news post saved through the admin panel, read from the
database in KAISH_DATA_DIR (default ./instance). Without a database it uses site.json alone.

A static copy can't sign anyone in or save edits: run app.py for that.
"""
import shutil
import sqlite3

import db as dbm
import renderer as R

ROOT = R.ROOT
ADMIN_ONLY = {"admin.css", "edit.css", "edit.js"}


def load_content():
    if not dbm.DB_PATH.exists():
        return {}, {}, [], set()
    con = sqlite3.connect(dbm.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        try:
            hidden = dbm.hidden(con)
        except sqlite3.OperationalError:
            hidden = set()
        return dbm.settings(con), dbm.text_overrides(con), dbm.published_posts(con), hidden
    except sqlite3.OperationalError:
        return {}, {}, [], set()
    finally:
        con.close()


def build(target, endpoint, bare_index, values, texts, posts, hidden=frozenset()):
    out_dir = ROOT / target
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True)
    for f in (ROOT / "assets").iterdir():
        if f.is_file() and f.name not in ADMIN_ONLY:
            shutil.copy(f, out_dir / "assets" / f.name)

    hidden = set(hidden) | {("page", "universities")}  # university pages need the server, so the static copy leaves them out

    def renderer():
        return R.Renderer(values=values, texts=texts, posts=posts, endpoint=endpoint, hidden=hidden)

    written = []
    for lang, name, meta, _body in R.page_sources():
        if name == "news-post" or meta.get("dynamic") or ("page", name) in hidden:  # member pages need the server
            continue
        out = R.out_path(lang, meta)
        full = not (bare_index and out == "index.html")  # an artifact wraps its main page itself
        dest = out_dir / out
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(renderer().render(lang, name, full=full), encoding="utf-8")
        written.append(out)
    shutil.copy(ROOT / "assets" / "favicon.ico", out_dir / "favicon.ico")
    pic = (values.get("hero_image") or "").strip()
    if pic and (dbm.UPLOADS / pic).exists():
        (out_dir / "uploads").mkdir(exist_ok=True)
        shutil.copy(dbm.UPLOADS / pic, out_dir / "uploads" / pic)
    for post in posts:
        for lang in ("en", "ku"):
            out = f"{R.UI[lang]['base']}news/{post['slug']}.html"
            dest = out_dir / out
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(renderer().render_post(lang, post), encoding="utf-8")
            written.append(out)
        if post.get("image") and (dbm.UPLOADS / post["image"]).exists():
            (out_dir / "uploads").mkdir(exist_ok=True)
            shutil.copy(dbm.UPLOADS / post["image"], out_dir / "uploads" / post["image"])
    return written


def main():
    settings, texts, posts, hidden = load_content()
    site = R.load_site()["values"]
    values = dict(site)
    values.update(settings)
    endpoint = (values.get("form_endpoint") or "").strip()
    pages = build("dist", endpoint, False, values, texts, posts, hidden)
    build("preview", "", True, values, texts, posts, hidden)
    missing = [k for k, v in values.items()
               if not str(v).strip() and k not in ("domain", "form_endpoint") and not k.endswith("_ku")]
    print(f"Built {len(pages)} pages ({len(posts)} news posts, {len(texts)} edited texts) into dist/ and preview/")
    print(f"{len(missing)} details still empty (shown on the site as [placeholders]).")
    if not endpoint:
        print("No form_endpoint: in this static copy the forms show a confirmation but send nothing.")


if __name__ == "__main__":
    main()
