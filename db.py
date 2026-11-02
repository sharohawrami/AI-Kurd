"""SQLite storage for the Kurdistan AI Safety Hub app: admins, text edits, settings,
news and events, form submissions and an activity log."""
import datetime
import json
import os
import pathlib
import secrets
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent
DATA_DIR = pathlib.Path(os.environ.get("KAISH_DATA_DIR", ROOT / "instance")).resolve()
DB_PATH = DATA_DIR / "kaish.db"
UPLOADS = DATA_DIR / "uploads"
MEMBER_PHOTOS = UPLOADS / "members"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  display_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('superadmin', 'admin', 'university')),
  active INTEGER NOT NULL DEFAULT 1,
  must_change_password INTEGER NOT NULL DEFAULT 1,
  session_token TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by INTEGER,
  last_login TEXT,
  university_id INTEGER
);
CREATE TABLE IF NOT EXISTS texts (
  lang TEXT NOT NULL,
  scope TEXT NOT NULL,
  key TEXT NOT NULL,
  original TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by INTEGER,
  PRIMARY KEY (lang, scope, key)
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by INTEGER
);
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL DEFAULT 'news' CHECK (kind IN ('news', 'event')),
  slug TEXT NOT NULL UNIQUE,
  title_en TEXT NOT NULL DEFAULT '', title_ku TEXT NOT NULL DEFAULT '',
  summary_en TEXT NOT NULL DEFAULT '', summary_ku TEXT NOT NULL DEFAULT '',
  body_en TEXT NOT NULL DEFAULT '', body_ku TEXT NOT NULL DEFAULT '',
  image TEXT NOT NULL DEFAULT '',
  image_alt_en TEXT NOT NULL DEFAULT '', image_alt_ku TEXT NOT NULL DEFAULT '',
  event_date TEXT NOT NULL DEFAULT '', event_time TEXT NOT NULL DEFAULT '',
  location_en TEXT NOT NULL DEFAULT '', location_ku TEXT NOT NULL DEFAULT '',
  published INTEGER NOT NULL DEFAULT 0,
  published_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  created_by INTEGER,
  updated_by INTEGER,
  university_id INTEGER
);
CREATE TABLE IF NOT EXISTS universities (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name_en TEXT NOT NULL,
  name_ku TEXT NOT NULL DEFAULT '',
  name_key TEXT NOT NULL UNIQUE,
  city_en TEXT NOT NULL DEFAULT '',
  city_ku TEXT NOT NULL DEFAULT '',
  website TEXT NOT NULL DEFAULT '',
  about_en TEXT NOT NULL DEFAULT '',
  about_ku TEXT NOT NULL DEFAULT '',
  logo TEXT NOT NULL DEFAULT '',
  published INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY,
  university_id INTEGER NOT NULL,
  slug TEXT NOT NULL,
  title_en TEXT NOT NULL DEFAULT '', title_ku TEXT NOT NULL DEFAULT '',
  summary_en TEXT NOT NULL DEFAULT '', summary_ku TEXT NOT NULL DEFAULT '',
  details_en TEXT NOT NULL DEFAULT '', details_ku TEXT NOT NULL DEFAULT '',
  location_en TEXT NOT NULL DEFAULT '', location_ku TEXT NOT NULL DEFAULT '',
  starts TEXT NOT NULL DEFAULT '',
  deadline TEXT NOT NULL DEFAULT '',
  questions TEXT NOT NULL DEFAULT '[]',
  accepting INTEGER NOT NULL DEFAULT 1,
  published INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (university_id, slug)
);
CREATE TABLE IF NOT EXISTS submissions (
  id INTEGER PRIMARY KEY,
  form TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  data TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  action TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL,
  name_ku TEXT NOT NULL DEFAULT '',
  occupation TEXT NOT NULL DEFAULT '',
  city TEXT NOT NULL DEFAULT '',
  bio TEXT NOT NULL DEFAULT '',
  interests TEXT NOT NULL DEFAULT '',
  link TEXT NOT NULL DEFAULT '',
  picture TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'en',
  active INTEGER NOT NULL DEFAULT 1,
  must_change_password INTEGER NOT NULL DEFAULT 0,
  session_token TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_login TEXT
);
CREATE TABLE IF NOT EXISTS hidden (
  scope TEXT NOT NULL,
  key TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by INTEGER,
  PRIMARY KEY (scope, key)
);
CREATE TABLE IF NOT EXISTS login_attempts (
  key TEXT PRIMARY KEY,
  failures INTEGER NOT NULL,
  first_at REAL NOT NULL,
  locked_until REAL NOT NULL DEFAULT 0
);
"""


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEMBER_PHOTOS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def init(con):
    con.executescript(SCHEMA)
    con.commit()
    migrate(con)


def migrate(con):
    """Bring a database made by an earlier version up to date, keeping every row."""
    level = con.isolation_level
    con.isolation_level = None
    try:
        con.execute("BEGIN IMMEDIATE")
        users_sql = con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone()[0]
        if "'university'" not in users_sql:
            con.execute("""CREATE TABLE users_new (
              id INTEGER PRIMARY KEY,
              username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              display_name TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK (role IN ('superadmin', 'admin', 'university')),
              active INTEGER NOT NULL DEFAULT 1,
              must_change_password INTEGER NOT NULL DEFAULT 1,
              session_token TEXT NOT NULL,
              created_at TEXT NOT NULL,
              created_by INTEGER,
              last_login TEXT,
              university_id INTEGER)""")
            con.execute("""INSERT INTO users_new (id, username, display_name, password_hash, role, active,
              must_change_password, session_token, created_at, created_by, last_login)
              SELECT id, username, display_name, password_hash, role, active, must_change_password, session_token,
              created_at, created_by, last_login FROM users""")
            con.execute("DROP TABLE users")
            con.execute("ALTER TABLE users_new RENAME TO users")
        post_cols = [r[1] for r in con.execute("PRAGMA table_info(posts)")]
        if "university_id" not in post_cols:
            con.execute("ALTER TABLE posts ADD COLUMN university_id INTEGER")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.isolation_level = level


def new_token():
    return secrets.token_urlsafe(24)


def log(con, user_id, action, detail=""):
    con.execute("INSERT INTO activity (user_id, action, detail, at) VALUES (?, ?, ?, ?)",
                (user_id, action, detail[:500], now()))


# ---------- reads used by the renderer ----------
def text_overrides(con):
    return {(r["lang"], r["scope"], r["key"]): r["value"]
            for r in con.execute("SELECT lang, scope, key, value FROM texts")}


def hidden(con):
    """{(scope, key)} of sections hidden by admins; ("page", name) for whole pages."""
    return {(r["scope"], r["key"]) for r in con.execute("SELECT scope, key FROM hidden")}


def settings(con):
    return {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM settings")}


def published_posts(con, university_id=None):
    """Published posts of the Hub itself, or of one university."""
    where = "university_id IS NULL" if university_id is None else "university_id = ?"
    args = () if university_id is None else (university_id,)
    rows = con.execute(
        f"SELECT * FROM posts WHERE published = 1 AND {where} ORDER BY "
        "COALESCE(NULLIF(published_at, ''), created_at) DESC, id DESC", args).fetchall()
    return [dict(r) for r in rows]


def submission_fields(row):
    try:
        return json.loads(row["data"])
    except (TypeError, ValueError):
        return {}


# ---------- accounts ----------
_WORDS = ["Zagros", "Hawler", "Kilim", "Saffron", "Madder", "Indigo", "Newroz", "Halgurd", "Sirwan",
          "Loom", "Qelat", "Dukan", "Amedi", "Bekhal", "Jamadani", "Pira", "Gali", "Safin"]
_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def temp_password():
    """A one-time password that is easy to read aloud: Word-xxxx-Word-xxxx (about 57 bits)."""
    chunk = lambda: "".join(secrets.choice(_CHARS) for _ in range(4))
    return f"{secrets.choice(_WORDS)}-{chunk()}-{secrets.choice(_WORDS)}-{chunk()}"


def create_user(con, username, display_name, password_hash, role, must_change=True, created_by=None):
    con.execute("INSERT INTO users (username, display_name, password_hash, role, active, must_change_password, "
                "session_token, created_at, created_by) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)",
                (username, display_name, password_hash, role, int(must_change), new_token(), now(), created_by))
