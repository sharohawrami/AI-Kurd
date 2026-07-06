from flask import Blueprint, render_template
from data.store import load, TOOL_CATEGORIES

resources_bp = Blueprint("resources", __name__)


@resources_bp.route("/")
def index():
    return render_template(
        "resources.html",
        active_page="resources",
        tools=load("tools"),
        categories=TOOL_CATEGORIES,
        tutorials=load("tutorials"),
    )
