# Daily Energy page — daily boost + mood-based responses.
# The free-text AI chat lives on its own page now: AI Kurd Bot (/bot).

from datetime import date

from flask import Blueprint, render_template

from data.store import load

energy_bp = Blueprint("energy", __name__)


@energy_bp.route("/")
def index():
    boosts = load("boosts")
    boost = boosts[date.today().toordinal() % len(boosts)] if boosts else {}
    return render_template(
        "energy.html",
        active_page="daily",
        boost=boost,
        moods=load("moods"),
    )
