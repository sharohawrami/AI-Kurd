# Deploying AI Kurd — read this BEFORE connecting a domain

## Why your changes disappeared last time

Admin edits are saved as files (JSON + uploaded images). On most hosting
platforms the app folder is **ephemeral**: every restart or redeploy resets
it to what you deployed, and anything written after that is deleted. Some
hosts even make the folder read-only, so saves fail silently.

The fix: store data on a **persistent disk** and tell the app where it is.

## Setup (2 environment variables)

| Variable          | Value                                          |
|-------------------|------------------------------------------------|
| `AIKURD_DATA_DIR` | A folder on a persistent disk, e.g. `/var/data/aikurd` |
| `SECRET_KEY`      | A long random string (keeps admins logged in across restarts) |

On first start the app copies its seed data into `AIKURD_DATA_DIR`
automatically. Uploaded images also go there (`uploads/`), served at `/uploads/...`.

Generate a secret key:

    python3 -c "import secrets; print(secrets.token_hex(32))"

## Per-host notes

- **Render**: add a "Persistent Disk" (e.g. mounted at `/var/data`), then set
  `AIKURD_DATA_DIR=/var/data/aikurd`. Without the disk, data WILL be lost.
- **Railway**: add a "Volume", mount it (e.g. `/data`), set
  `AIKURD_DATA_DIR=/data/aikurd`.
- **VPS (DigitalOcean, Hetzner, etc.)**: any folder works, e.g.
  `AIKURD_DATA_DIR=/home/youruser/aikurd-data`.
- **PythonAnywhere**: disk is persistent by default; still set
  `AIKURD_DATA_DIR=/home/youruser/aikurd-data` so data lives outside the
  code folder (redeploying code won't touch it).
- **Vercel / Netlify / GitHub Pages**: NOT suitable — no persistent writable
  disk for Flask apps.

## Run with a production server (not `python app.py`)

    pip install gunicorn
    gunicorn -w 1 -b 0.0.0.0:8000 app:app

Note: keep `-w 1` (one worker). The JSON store is safe within one process;
with multiple workers, simultaneous edits could overwrite each other.
For multiple workers, migrate to SQLite/Postgres first.

## Safety nets built into the app

- If a save fails, the admin panel now shows a big red **SAVE FAILED**
  message instead of pretending it worked.
- **⬇ Download backup** button in the dashboard exports all data + uploaded
  images as a zip. Download one before every redeploy.
- Writes are atomic (temp file + rename) so a crash can't corrupt data.

## Checklist before pointing your domain

1. Persistent disk mounted, `AIKURD_DATA_DIR` set to it
2. `SECRET_KEY` set
3. Running under gunicorn, `debug=False` (gunicorn ignores app.run)
4. Log in → change the default password
5. Make a test edit → restart the app → confirm the edit survived
6. Download a backup
