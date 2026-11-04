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

## Round 3
- **Western digits everywhere.** Aria draws 0-9 in Persian shapes, so a tiny digits-only font (`static/fonts/KurdishDigits.woff2`) now sits first in the Kurdish font stack and takes over only for 0-9. Content typed with ٠-٩ / ۰-۹ in the admin is also converted to 0-9 when rendered (see `western_digits` in `app.py`).

## Round 4 — videos + image crop
- **Videos in articles.** New `video` field: paste a YouTube / Vimeo link, or upload an MP4/WebM/MOV file (`video_file`) in the admin panel. The article page shows a player instead of the cover (the article image becomes the poster); cards get a play badge. Upload limit defaults to 500 MB — set `MAX_UPLOAD_MB` to change it (and raise your reverse proxy's limit, e.g. nginx `client_max_body_size`).
- **Crop & preview after choosing an image.** Pick a file → a crop editor appears: choose 16:9 / 16:10 / 4:3 / 1:1, zoom with the slider, drag to reposition, and see a live preview of the article card. The crop is applied automatically when you press Save/Add (saved as 1600px JPEG). "Use original" skips cropping. No external libraries (`static/js/admin.js`).
