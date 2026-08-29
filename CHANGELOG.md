# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-29

A substantial reliability, security, and quality overhaul.

### Added
- Background job model: scrapes run on a worker thread; the UI polls
  `/status/<job_id>` for live progress instead of freezing the request.
- New endpoints: `POST /scrape`, `GET /status/<job_id>`,
  `GET /download/<job_id>`, and `GET /health`.
- Per-job CSV files under `OUTPUT_DIR`, so concurrent users never collide.
- Redesigned single-page UI with a live status console, progress bar, and an
  in-browser results preview table.
- Environment-based configuration (`config.py`, `.env.example`).
- `scraper.py` with a pure, unit-tested `parse_videos()` function.
- Test suite (`pytest`) covering routes, job lifecycle, and HTML parsing.
- Continuous integration (GitHub Actions) running ruff + pytest on 3.9–3.12.
- `Dockerfile`, `.dockerignore`, and `docker-compose.yml` bundling Chromium.
- Linting/formatting config (`pyproject.toml` / ruff) and dev requirements.
- Issue and pull-request templates.

### Changed
- Channel discovery now uses YouTube's own search results instead of scraping
  Google, avoiding Google CAPTCHAs and improving reliability.
- Scrolling loads videos until the page height stabilizes (with timeout and
  round caps) rather than a fixed, always-slow scroll budget.
- Video titles are read from the title anchor's attributes/text, fixing the
  frequently-empty title field.
- Chrome runs headless and configurably; production defaults are safe
  (`FLASK_DEBUG` off unless explicitly enabled).
- README and CONTRIBUTING rewritten for the new architecture.

### Removed
- `tqdm` dependency (replaced by an internal progress callback).
- The shared, single `data.csv` output path.

### Security
- The Werkzeug debugger is disabled by default and gated behind `FLASK_DEBUG`.
- Input length validation on the company field.
- Container runs as a non-root user.
