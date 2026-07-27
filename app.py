# =============================================================
# AI Kurd — Main Flask Application (modular, blueprint-based)
# =============================================================

import os

from flask import Flask, render_template, send_from_directory

from data.store import UPLOADS_DIR, init_data_dir


def load_dotenv():
    """Load KEY=VALUE lines from a .env file next to app.py (if present).
    Real environment variables always win over .env values."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


def create_app():
    load_dotenv()
    init_data_dir()  # ensure persistent data dir exists & is seeded

    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False  # UTF-8 for Kurdish/Arabic
    # Set SECRET_KEY as an environment variable in production!
    app.secret_key = os.environ.get("SECRET_KEY", "aikurd-dev-secret-change-me")

    from routes.main import main_bp
    from routes.resources import resources_bp
    from routes.safety import safety_bp
    from routes.prompts import prompts_bp
    from routes.projects import projects_bp
    from routes.energy import energy_bp
    from routes.bot import bot_bp
    from routes.articles import articles_bp
    from routes.about import about_bp
    from routes.services import services_bp
    from routes.admin import admin_bp
    from routes.seo import seo_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(resources_bp, url_prefix="/resources")
    app.register_blueprint(safety_bp, url_prefix="/ai-safety")
    app.register_blueprint(prompts_bp, url_prefix="/prompts")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(energy_bp, url_prefix="/daily")
    app.register_blueprint(bot_bp, url_prefix="/bot")
    app.register_blueprint(articles_bp, url_prefix="/articles")
    app.register_blueprint(about_bp, url_prefix="/about")
    app.register_blueprint(services_bp, url_prefix="/services")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(seo_bp)  # /robots.txt, /llms.txt, /sitemap.xml

    # Uploaded images are stored in the persistent data dir, not in static/
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(UPLOADS_DIR, filename)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html", active_page=None), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("404.html", active_page=None), 403

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
