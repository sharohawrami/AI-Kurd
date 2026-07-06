# AI Kurd Bot — bilingual chat assistant powered by the Claude API.
# Activates when ANTHROPIC_API_KEY is set (in .env or environment).
# Includes a simple per-IP rate limit to protect your API credit.

import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict

from flask import Blueprint, jsonify, render_template, request

bot_bp = Blueprint("bot", __name__)

SYSTEM_PROMPT = (
    "You are AI Kurd Bot (بۆتی AI Kurd), the friendly assistant of AI Kurd — "
    "a Kurdish platform for AI education, tech tutorials, and AI Safety. "
    "You help visitors learn about artificial intelligence, technology, "
    "programming, study skills, and AI Safety, and you can also offer warm "
    "encouragement when someone shares how they feel. "
    "Reply in the language the visitor uses: Kurdish (Sorani) or English. "
    "When replying in Kurdish, write natural, fluent Central Kurdish (Sorani) "
    "in Arabic script, the way an educated native speaker from Slemani or "
    "Hewlêr would write — never a word-for-word translation from English. "
    "Prefer common Kurdish words over Arabic or Persian loanwords when a "
    "natural Kurdish word exists. Keep technical terms like AI, API, or "
    "model in Latin script if that is how Kurdish speakers commonly write "
    "them. Do not mix English sentences into a Kurdish reply. "
    "Be friendly, clear, and concise — usually under 200 words. Use simple "
    "language; visitors may be students or beginners. "
    "You are not a doctor or therapist: for serious medical or emotional "
    "issues, gently suggest talking to a professional or someone they trust. "
    "If asked about the AI Kurd website, it has: a Resource Hub with AI tools "
    "and tutorials, an AI Safety Hub, a Prompt Library, a Projects page, and "
    "a Daily Energy page."
)

# Model routing: Kurdish needs a stronger model to sound natural.
MODEL_EN = "claude-haiku-4-5-20251001"   # cheap, fine for English
MODEL_KU = "claude-sonnet-5"             # much better Kurdish (~5x cost)


def _is_kurdish(text):
    """True if the text contains Arabic-script characters."""
    return any("؀" <= ch <= "ۿ" or "ݐ" <= ch <= "ݿ" for ch in text)

# ---- simple in-memory rate limit (fine with a single gunicorn worker) ----
RATE_LIMIT = 20          # messages
RATE_WINDOW = 60 * 60    # per hour
_hits = defaultdict(list)


def _rate_limited(ip):
    now = time.time()
    _hits[ip] = [t for t in _hits[ip] if now - t < RATE_WINDOW]
    if len(_hits[ip]) >= RATE_LIMIT:
        return True
    _hits[ip].append(now)
    return False


def ai_enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@bot_bp.route("/")
def index():
    return render_template("bot.html", active_page="bot", ai_enabled=ai_enabled())


@bot_bp.route("/chat", methods=["POST"])
def chat():
    if not ai_enabled():
        return jsonify({"error": "AI Kurd Bot is not enabled yet."}), 503

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    if _rate_limited(ip):
        return jsonify({"error": "You've sent a lot of messages — please try again in a while. / نامەی زۆرت ناردووە — تکایە دواتر هەوڵ بدەرەوە."}), 429

    body = request.get_json(silent=True) or {}
    raw = body.get("messages", [])
    messages = []
    for m in raw[-12:]:  # keep the last 12 turns
        role = m.get("role")
        content = str(m.get("content", "")).strip()[:2000]
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    if not messages or messages[-1]["role"] != "user":
        return jsonify({"error": "Please write a message first."}), 400

    payload = {
        "model": MODEL_KU if _is_kurdish(messages[-1]["content"]) else MODEL_EN,
        "max_tokens": 700,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
    )
    last_err = None
    for attempt in range(3):  # auto-retry: unstable connections drop requests
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
            # The reply may contain several content blocks (e.g. a
            # "thinking" block before the "text" block) — join all text.
            reply = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            ).strip()
            if not reply:
                raise ValueError("empty reply from API")
            return jsonify({"reply": reply})
        except urllib.error.HTTPError as e:
            # Real API errors — don't retry, explain the cause
            try:
                detail = json.load(e).get("error", {}).get("message", "")
            except Exception:
                detail = ""
            print(f"[AI Kurd Bot] API error {e.code}: {detail}", flush=True)
            if e.code == 401:
                msg = "The API key is invalid or revoked. Check the key in your .env file."
            elif "credit" in detail.lower() or "billing" in detail.lower():
                msg = "The Anthropic account has no credit yet. Add credit at console.anthropic.com → Billing."
            elif e.code == 404 or "model" in detail.lower():
                msg = f"The AI model was not accepted: {detail}"
            elif e.code == 429:
                msg = "The AI service is busy (rate limit). Try again in a minute."
            else:
                msg = f"AI service error ({e.code}). Try again later."
            return jsonify({"error": msg}), 502
        except Exception as e:
            last_err = e
            print(f"[AI Kurd Bot] attempt {attempt + 1}/3 failed: {e}", flush=True)
            time.sleep(1.5 * (attempt + 1))
    print(f"[AI Kurd Bot] all retries failed: {last_err}", flush=True)
    return jsonify({"error": "The connection keeps dropping — please send your message again. / پەیوەندییەکە بڕایەوە — تکایە نامەکەت دووبارە بنێرەرەوە."}), 502
