# Articles — full content system with per-article pages.
# Bodies support simple formatting: blank line = new paragraph,
# "## " at line start = heading, **bold**.

import html
import re
from datetime import date, datetime

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
            parts.append(f"<h2>{block[3:]}</h2>")
        else:
            parts.append(f'<p style="white-space:pre-line">{block}</p>')
    return Markup("\n".join(parts))


# ---------- template filters (registered on the blueprint's app) ----------

def timeago(value):
    """'2026-06-28' → '3 months ago'. Falls back to the raw string."""
    if not value:
        return ""
    try:
        d = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return value
    days = (date.today() - d).days
    if days < 0:
        return d.strftime("%b %d, %Y")
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        w = days // 7
        return f"{w} week{'s' if w > 1 else ''} ago"
    if days < 365:
        m = days // 30
        return f"{m} month{'s' if m > 1 else ''} ago"
    y = days // 365
    return f"{y} year{'s' if y > 1 else ''} ago"


def timeago_ku(value):
    """Kurdish (Sorani) version of timeago."""
    if not value:
        return ""
    try:
        d = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return value
    days = (date.today() - d).days
    if days <= 0:
        return "ئەمڕۆ"
    if days == 1:
        return "دوێنێ"
    if days < 7:
        return f"{days} ڕۆژ لەمەوبەر"
    if days < 30:
        return f"{days // 7} هەفتە لەمەوبەر"
    if days < 365:
        return f"{days // 30} مانگ لەمەوبەر"
    return f"{days // 365} ساڵ لەمەوبەر"


def reading_time(text):
    words = len(re.findall(r"\S+", text or ""))
    return max(1, round(words / 200))


def nice_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        return value


@articles_bp.app_template_filter("timeago")
def _timeago(v):
    return timeago(v)


@articles_bp.app_template_filter("timeago_ku")
def _timeago_ku(v):
    return timeago_ku(v)


@articles_bp.app_template_filter("reading_time")
def _reading_time(v):
    return reading_time(v)


@articles_bp.app_template_filter("nice_date")
def _nice_date(v):
    return nice_date(v)


# ---------- helpers ----------

def sorted_articles():
    return sorted(load("articles"), key=lambda a: a.get("date", ""), reverse=True)


def article_types(articles):
    seen = []
    for a in articles:
        t = (a.get("type") or "").strip()
        if t and t not in seen:
            seen.append(t)
    return seen


# ---------- routes ----------

@articles_bp.route("/")
def index():
    articles = sorted_articles()
    featured = articles[0] if articles else None
    with_image = [a for a in articles[1:] if a.get("image")]
    # The "Recommended" column: prefer articles that have a picture for the lead slot.
    recommended = (with_image[:1] + [a for a in articles[1:] if a not in with_image[:1]])[:5]
    return render_template(
        "articles.html",
        active_page="articles",
        articles=articles,
        featured=featured,
        recommended=recommended,
        strip=articles[1:4],
        types=article_types(articles),
    )


@articles_bp.route("/<slug>")
def detail(slug):
    articles = sorted_articles()
    article = next((a for a in articles if a.get("slug") == slug), None)
    if not article:
        abort(404)
    others = [a for a in articles if a is not article]
    same_type = [a for a in others if a.get("type") == article.get("type")]
    related = (same_type + [a for a in others if a not in same_type])[:4]
    idx = articles.index(article)
    return render_template(
        "article.html",
        active_page="articles",
        a=article,
        body_en=render_body(article.get("body_en", "")),
        body_ku=render_body(article.get("body_ku", "")),
        related=related,
        prev_article=articles[idx + 1] if idx + 1 < len(articles) else None,
        next_article=articles[idx - 1] if idx > 0 else None,
    )
