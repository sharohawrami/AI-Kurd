# =============================================================
# SEO / AI-visibility routes: robots.txt, llms.txt, sitemap.xml
#
# These make the site readable by search engines AND by AI crawlers
# (ChatGPT, Claude, Perplexity, Gemini, Copilot, etc.).
#
# Set SITE_URL in your environment to your real domain, e.g.
#   SITE_URL=https://aikurd.org
# =============================================================

import os
from datetime import date

from flask import Blueprint, Response, current_app, request

from data.store import load

seo_bp = Blueprint("seo", __name__)


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
        if path.startswith(("/admin", "/static", "/uploads")):
            continue
        # Skip machine endpoints and the SEO files themselves
        if "/api" in path or path in ("/robots.txt", "/sitemap.xml", "/llms.txt"):
            continue
        urls.append((base + path.rstrip("/") if path != "/" else base, None))

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
        out.append(f"    <priority>{'1.0' if loc == base else '0.7'}</priority>")
        out.append("  </url>")
    out.append("</urlset>")
    return Response("\n".join(out), mimetype="application/xml")


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
