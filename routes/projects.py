from flask import Blueprint, render_template
from data.store import load

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/")
def index():
    return render_template(
        "projects.html",
        active_page="projects",
        projects=load("projects"),
    )
