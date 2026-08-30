"""Flask web application (application-factory pattern).

Endpoints
---------
GET  /                 -> the single-page UI
POST /scrape           -> start a scrape job; returns {job_id} (202)
GET  /status/<job_id>  -> job status + progress + preview (JSON)
GET  /download/<job_id>-> the generated CSV (attachment)
GET  /health           -> liveness probe (JSON)

Scraping runs on a background thread via ``JobManager`` so requests return
immediately and the browser polls ``/status`` for progress.
"""

from __future__ import annotations

import logging
import secrets

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_file,
)

from config import Config
from jobs import JobManager, JobStatus
from scraper import scrape_channel


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
    )


def create_app(config: Config | None = None, job_manager: JobManager | None = None) -> Flask:
    """Build and configure the Flask app.

    Args are injectable so tests can pass a custom ``Config`` and a
    ``JobManager`` wired to a fake scraper (no real browser).
    """
    config = config or Config()
    _configure_logging(config.LOG_LEVEL)
    logger = logging.getLogger(__name__)

    app = Flask(__name__)

    # Secret key: use the configured one, or generate an ephemeral key in dev
    # (with a warning) so the app still boots.
    if config.SECRET_KEY:
        app.secret_key = config.SECRET_KEY
    else:
        app.secret_key = secrets.token_hex(32)
        logger.warning(
            "SECRET_KEY not set — generated a temporary key. Set SECRET_KEY in "
            "the environment for stable sessions."
        )

    config.ensure_output_dir()

    # Default job manager wires the real scraper with tuning from config.
    if job_manager is None:
        job_manager = JobManager(
            output_dir=config.OUTPUT_DIR,
            scrape_fn=scrape_channel,
            scrape_kwargs={
                "headless": config.HEADLESS,
                "chrome_binary": config.CHROME_BINARY,
                "scrape_timeout": config.SCRAPE_TIMEOUT,
                "scroll_pause": config.SCROLL_PAUSE,
                "scroll_max_stale": config.SCROLL_MAX_STALE,
                "scroll_max_rounds": config.SCROLL_MAX_ROUNDS,
                "element_timeout": config.ELEMENT_TIMEOUT,
            },
        )

    app.config["APP_CONFIG"] = config
    app.config["JOB_MANAGER"] = job_manager

    # ----------------------------------------------------------------- routes
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/scrape")
    def scrape():
        company = (request.form.get("company") or "").strip()
        if not company:
            return jsonify(error="Please enter a company name."), 400
        if len(company) > config.MAX_COMPANY_LEN:
            return (
                jsonify(
                    error=f"Company name is too long "
                    f"(max {config.MAX_COMPANY_LEN} characters)."
                ),
                400,
            )
        job = job_manager.submit(company)
        logger.info("Submitted job %s for '%s'", job.id, company)
        return jsonify(job_id=job.id, status=job.status.value), 202

    @app.get("/status/<job_id>")
    def status(job_id: str):
        job = job_manager.get(job_id)
        if job is None:
            return jsonify(error="Unknown job id."), 404
        return jsonify(job.to_public_dict())

    @app.get("/download/<job_id>")
    def download(job_id: str):
        job = job_manager.get(job_id)
        if job is None:
            abort(404, description="Unknown job id.")
        if job.status != JobStatus.DONE or not job.csv_path or not job.csv_path.exists():
            abort(409, description="This job's file is not ready yet.")
        safe_company = "".join(
            c for c in job.company if c.isalnum() or c in (" ", "-", "_")
        ).strip().replace(" ", "_") or "youtube"
        return send_file(
            job.csv_path,
            as_attachment=True,
            download_name=f"{safe_company}_videos.csv",
            mimetype="text/csv",
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    # -------------------------------------------------------------- errors
    @app.errorhandler(404)
    def not_found(err):
        if request.path.startswith(("/status", "/download", "/scrape")):
            return jsonify(error=getattr(err, "description", "Not found.")), 404
        return render_template("index.html", error="Page not found."), 404

    @app.errorhandler(409)
    def conflict(err):
        return jsonify(error=getattr(err, "description", "Conflict.")), 409

    @app.errorhandler(500)
    def server_error(err):  # pragma: no cover - defensive
        logger.exception("Internal server error")
        return jsonify(error="Internal server error."), 500

    return app


# Module-level app for `flask run` / gunicorn ("app:app").
app = create_app()


if __name__ == "__main__":
    cfg = app.config["APP_CONFIG"]
    # debug is driven by config (FLASK_DEBUG) and defaults to OFF.
    app.run(host=cfg.HOST, port=cfg.PORT, debug=cfg.DEBUG)
