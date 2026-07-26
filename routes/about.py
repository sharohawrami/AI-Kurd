from flask import Blueprint, render_template

from data.store import load

about_bp = Blueprint("about", __name__)


@about_bp.route("/")
def index():
    return render_template("about.html", active_page="about",
                           about=load("about", {}),
                           owners=load("owners", []))
