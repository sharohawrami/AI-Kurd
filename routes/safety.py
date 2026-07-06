from flask import Blueprint, render_template

safety_bp = Blueprint("safety", __name__)


@safety_bp.route("/")
def index():
    return render_template("safety.html", active_page="safety")
