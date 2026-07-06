from flask import Blueprint, render_template, jsonify
from data.store import load, PROMPT_CATEGORIES

prompts_bp = Blueprint("prompts", __name__)


@prompts_bp.route("/")
def index():
    return render_template(
        "prompts.html",
        active_page="prompts",
        prompts=load("prompts"),
        categories=PROMPT_CATEGORIES,
    )


@prompts_bp.route("/api")
def api():
    return jsonify(load("prompts"))
