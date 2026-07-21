from flask import Blueprint, render_template

from data.store import load

services_bp = Blueprint("services", __name__)


@services_bp.route("/")
def index():
    return render_template("services.html", active_page="services",
                           services=load("services", {}))
