# JSON data store — every collection is an editable .json file.
#
# PERSISTENCE (important for deployment!):
# By default data lives next to this file. On most hosting platforms the
# app's own folder is EPHEMERAL — anything written there is lost on every
# restart or redeploy. Before connecting a domain, set the environment
# variable AIKURD_DATA_DIR to a folder on a PERSISTENT disk/volume, e.g.:
#
#   AIKURD_DATA_DIR=/var/data/aikurd
#
# On first run the seed data is copied there automatically.

import json
import os
import shutil
import threading

_SEED_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("AIKURD_DATA_DIR", _SEED_DIR)
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

_lock = threading.Lock()

TOOL_CATEGORIES = ["Productivity", "Coding", "Research"]
PROMPT_CATEGORIES = ["Image", "Learning", "Writing", "Coding", "Research"]


def init_data_dir():
    """Create the data dir and copy seed .json files there on first run."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    if os.path.abspath(DATA_DIR) == os.path.abspath(_SEED_DIR):
        return
    for fname in os.listdir(_SEED_DIR):
        if fname.endswith(".json"):
            dest = os.path.join(DATA_DIR, fname)
            if not os.path.exists(dest):
                shutil.copy2(os.path.join(_SEED_DIR, fname), dest)


def _path(name):
    return os.path.join(DATA_DIR, name + ".json")


def load(name, default=None):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else []


def save(name, data):
    """Atomic write: dump to a temp file, then replace. Raises on failure
    so problems are VISIBLE instead of silently losing changes."""
    with _lock:
        tmp = _path(name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _path(name))
