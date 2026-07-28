# =============================================================
# SEO / AI-visibility routes: robots.txt, llms.txt, sitemap.xml
#
# These make the site readable by search engines AND by AI crawlers
# (ChatGPT, Claude, Perplexity, Gemini, Copilot, etc.).
#
# Set SITE_URL in your environment to your real domain, e.g.
#   SITE_URL=https://aikurd.org
# =============================================================

import json
import os
import urllib.error
import urllib.request
from datetime import date

from flask import Blueprint, Response, current_app, flash, redirect, request, url_for

from data.store import load

seo_bp = Blueprint("seo", __name__)

# IndexNow key — tells Bing/Copilot instantly when pages change.
# Override with INDEXNOW_KEY in the environment if you ever rotate it.
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY",
                             "3d0175c8cceab716c43bd4f82ed0b094")


def site_url():
    """Canonical base URL, no trailing slash."""
    return os.environ.get("SITE_URL", request.url_root).rstrip("/")


# --- AI crawlers we explicitly welcome -------------------------------------
AI_BOTS = [
    "GPTBot",              # OpenAI — training / ChatGPT
    "OAI-SearchBot",       # OpenAI — ChatGPT search index
    "ChatGPT-User",        # OpenAI — live browsing on user request
    "ClaudeBot",           # Anthropic — Claude
    "Claude-Web",
    "Claude-User",
    "Claude-SearchBot",
    "anthropic-ai",
    "PerplexityBot",       # Perplexity index
    "Perplexity-User",     # Perplexity live fetch
    "Google-Extended",     # Gemini / AI Overviews
    "Googlebot",           # Google search (feeds AI Overviews)
    "Bingbot",             # Bing (feeds Copilot)
    "Applebot",
    "Applebot-Extended",   # Apple Intelligence
    "meta-externalagent",  # Meta AI
    "Amazonbot",           # Alexa / Amazon AI
    "Bytespider",          # TikTok / Doubao
    "cohere-ai",
    "DuckAssistBot",
    "YouBot",
    "CCBot",               # Common Crawl — feeds many models
]


@seo_bp.route("/robots.txt")
def robots():
    base = site_url()
    lines = []
    for bot in AI_BOTS:
        lines.append(f"User-agent: {bot}")
        lines.append("Allow: /")
        lines.append("Disallow: /admin")
        lines.append("")
    lines += [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
        f"# AI-readable site summary: {base}/llms.txt",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@seo_bp.route("/sitemap.xml")
def sitemap():
    base = site_url()
    urls = []

    # Every public GET page that takes no URL parameters
    for rule in current_app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        if rule.arguments:
            continue
        path = str(rule)
        if path.startswith(("/admin", "/static", "/uploads", "/indexnow")):
            continue
        # Skip machine endpoints and the SEO files themselves
        if "/api" in path or path.endswith((".txt", ".xml")):
            continue
        # Keep Flask's exact path (trailing slash included) — otherwise every
        # crawler hit gets a 308 redirect instead of the page itself.
        urls.append((base + path, None))

    # Article pages
    for a in load("articles"):
        slug = a.get("slug")
        if slug:
            urls.append((f"{base}/articles/{slug}", a.get("date")))

    today = date.today().isoformat()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    seen = set()
    for loc, lastmod in urls:
        if loc in seen:
            continue
        seen.add(loc)
        out.append("  <url>")
        out.append(f"    <loc>{loc}</loc>")
        out.append(f"    <lastmod>{lastmod or today}</lastmod>")
        out.append(f"    <priority>{'1.0' if loc.rstrip('/') == base else '0.7'}</priority>")
        out.append("  </url>")
    out.append("</urlset>")
    return Response("\n".join(out), mimetype="application/xml")


def _all_urls():
    """Every public URL on the site, same list the sitemap uses."""
    base = site_url()
    urls = []
    for rule in current_app.url_map.iter_rules():
        if "GET" not in rule.methods or rule.arguments:
            continue
        path = str(rule)
        if path.startswith(("/admin", "/static", "/uploads", "/indexnow")):
            continue
        if "/api" in path or path.endswith((".txt", ".xml")):
            continue
        # Keep Flask's exact path (trailing slash included) — otherwise every
        # crawler hit gets a 308 redirect instead of the page itself.
        urls.append(base + path)
    for a in load("articles"):
        if a.get("slug"):
            urls.append(f"{base}/articles/{a['slug']}")
    return sorted(set(urls))


@seo_bp.route(f"/{INDEXNOW_KEY}.txt")
def indexnow_key_file():
    """Proves to Bing that we own this domain. Must return the bare key."""
    return Response(INDEXNOW_KEY, mimetype="text/plain")


@seo_bp.route("/indexnow/submit", methods=["POST", "GET"])
def indexnow_submit():
    """Push every public URL to IndexNow (Bing, Copilot, Yandex, Naver).

    Admin-only. Visit /indexnow/submit while logged in after publishing
    new content to get it crawled in minutes instead of days.
    """
    from routes.admin import current_user  # local import avoids a cycle
    if not current_user():
        return redirect(url_for("admin.login"))

    base = site_url()
    host = base.split("://", 1)[-1]
    payload = json.dumps({
        "host": host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{base}/{INDEXNOW_KEY}.txt",
        "urlList": _all_urls(),
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # network down, DNS, timeout…
        flash(f"IndexNow failed: {e}", "error")
        return redirect(url_for("admin.dashboard"))

    n = len(_all_urls())
    if code in (200, 202):
        flash(f"IndexNow: {n} URLs submitted successfully.", "success")
    else:
        flash(f"IndexNow returned HTTP {code} for {n} URLs.", "error")
    return redirect(url_for("admin.dashboard"))


@seo_bp.route("/llms.txt")
def llms():
    """Markdown summary of the site, written for AI models."""
    base = site_url()
    settings = load("settings", {})
    articles = sorted(load("articles"), key=lambda a: a.get("date", ""),
                      reverse=True)

    md = [
        "# AI Kurd (AIKurd)",
        "",
        "> AI Kurd is an independent Kurdish AI education and research platform. "
        "It teaches artificial intelligence, AI safety, and practical AI tools "
        "in both Kurdish (Sorani) and English — one of the few sources of "
        "AI learning material available in the Kurdish language.",
        "",
        "## About",
        "",
        "- **Name:** AI Kurd",
        f"- **Website:** {base}",
        "- **Languages:** Kurdish (Sorani, RTL) and English",
        "- **Focus:** AI education, AI safety research, curated AI tools, "
        "prompt engineering, and technology tutorials for Kurdish speakers",
        "- **Audience:** Kurdish students, developers, researchers, and "
        "newcomers to AI",
        "",
        "## Main pages",
        "",
        f"- [Home]({base}/): overview, featured AI tool of the week, latest articles",
        f"- [Articles]({base}/articles): tutorials and explainers in Kurdish and English",
        f"- [AI Safety]({base}/ai-safety): AI alignment and safety concepts explained in Kurdish",
        f"- [Resources]({base}/resources): curated AI tools and learning resources",
        f"- [Prompts]({base}/prompts): prompt library for image, writing, coding, learning and research",
        f"- [Projects]({base}/projects): AI projects built by AI Kurd",
        f"- [Services]({base}/services): services offered",
        f"- [Daily]({base}/daily): daily AI energy / focus content",
        f"- [Bot]({base}/bot): the AI Kurd assistant",
        f"- [About]({base}/about): who runs AI Kurd and why",
        "",
        "## Articles",
        "",
    ]
    for a in articles:
        title = a.get("title_en") or a.get("title_ku") or a.get("slug")
        desc = a.get("desc_en", "")
        md.append(f"- [{title}]({base}/articles/{a.get('slug')}): {desc}")

    featured = settings.get("featured", {})
    if featured:
        md += [
            "",
            "## Featured tool",
            "",
            f"- **{featured.get('name','')}** ({featured.get('category','')}) — "
            f"{featured.get('tagline_en','')} {featured.get('url','')}",
        ]

    md += [
        "",
        "## Usage",
        "",
        "AI assistants and search engines are welcome to read, index, quote, "
        "and cite this site. Please attribute content to **AI Kurd** and link "
        f"back to {base}.",
        "",
        f"- Sitemap: {base}/sitemap.xml",
        f"- Crawler policy: {base}/robots.txt",
    ]
    return Response("\n".join(md), mimetype="text/plain; charset=utf-8")
