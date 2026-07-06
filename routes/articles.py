# Articles — full content system with per-article pages.
# Bodies support simple formatting: blank line = new paragraph,
# "## " at line start = heading, **bold**.

import html
import re

from flask import Blueprint, abort, render_template
from markupsafe import Markup

from data.store import load

articles_bp = Blueprint("articles", __name__)


def render_body(text):
    """Escape HTML, then apply minimal formatting (paragraphs, ##, **bold**)."""
    text = html.escape(text or "")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    parts = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("## "):
            parts.append(f'<h2 class="text-2xl font-black mt-10 mb-4">{block[3:]}</h2>')
        else:
            parts.append(f'<p class="text-white/70 leading-relaxed mb-5" style="white-space:pre-line">{block}</p>')
    return Markup("\n".join(parts))


def sorted_articles():
    return sorted(load("articles"), key=lambda a: a.get("date", ""), reverse=True)


@articles_bp.route("/")
def index():
    return render_template("articles.html", active_page="articles",
                           articles=sorted_articles())


@articles_bp.route("/<slug>")
def detail(slug):
    article = next((a for a in load("articles") if a.get("slug") == slug), None)
    if not article:
        abort(404)
    return render_template(
        "article.html",
        active_page="articles",
        a=article,
        body_en=render_body(article.get("body_en", "")),
        body_ku=render_body(article.get("body_ku", "")),
    )
