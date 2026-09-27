# What changed in this redesign

## Look & feel (all pages)
- New dark editorial design system: `static/css/site.css` (colors, cards, buttons, chips, panels, covers).
- Removed the animated canvas background (`ambient.js`). Replaced with a still spotlight + grain background.
- Tailwind is now compiled locally (`static/css/tailwind.css`) instead of the CDN script — no flash of unstyled content.
- New header: pill navigation, scroll-aware glass background, reading-progress line, clean mobile menu. Admin link moved to the footer / mobile menu.
- Kurdish font changed from Noto Sans Arabic to **Vazirmatn**, larger sizes and line-height. In Kurdish mode the whole layout mirrors to RTL.
- Cards have solid surfaces and higher-contrast text so they are readable.

## Articles
- `/articles/` rebuilt after the reference design: filter chips, search, "Best of the week" feature, recommended column with thumbnails, strip of next stories, then a full image grid of every article.
- `/articles/<slug>` shows the article picture as a wide cover, reading time, share / copy link, older/newer navigation, "More to read" sidebar, and Article structured data + Open Graph image.
- Articles without a picture get an automatically generated cover, so the layout never breaks.
- New template filters: `timeago`, `timeago_ku`, `reading_time`, `nice_date` (in `routes/articles.py`).

## Unchanged
- Admin panel, login, roles, uploads, backup and all JSON data files work exactly as before. Add an article with an image in the admin panel and it appears everywhere automatically.

## Round 2
- **Kurdish font**: Aria ExtraBold (`static/fonts/`), self-hosted, used for every Kurdish element. English stays Inter.
- **Favicon / logo**: rebuilt from the new logo picture (`static/img/favicon*.png`, `favicon.ico`, transparent `logo.png` for the header, `og.png` for social previews).
- **Home**: the hero now fills the first screen with the latest article beside the headline; on phones a compact "Latest" strip sits at the very top so it is always visible without scrolling.
- **Living background**: four AI/Kurdistan-themed scenes (`static/img/bg/`) crossfade and drift as you scroll. Replace them with your own 4K photos: drop files in `static/img/bg/` and edit the `BG_SCENES` list at the top of `<body>` in `templates/base.html`. (`tools/make_backgrounds.py` regenerates the built-in ones.)
- **PS5-style hover** (desktop): hovering an article, prompt or project card fades that card's picture into the page background, blurred and darkened, with a slow zoom. Cards without a picture simply don't trigger it.
