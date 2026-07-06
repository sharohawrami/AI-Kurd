from flask import Blueprint, render_template

from data.store import load

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    settings = load("settings", {})
    articles = sorted(load("articles"), key=lambda a: a.get("date", ""), reverse=True)
    return render_template(
        "index.html",
        active_page="home",
        settings=settings,
        featured_tool=settings.get("featured", {}),
        latest_content=articles[:6],
    )
