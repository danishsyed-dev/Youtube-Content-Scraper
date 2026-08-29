# YouTube Content Scraper

A Flask web application that collects a YouTube channel's full video catalog for
any company or creator and hands it back as a downloadable CSV. It uses
**Selenium** to drive a headless browser, **BeautifulSoup** to parse the loaded
page, and **pandas** to write the CSV.

Scraping runs as a **background job**, so the web request returns immediately and
the page shows live progress while videos load. Each job writes its own CSV, so
multiple people can use the app at once without clobbering each other's results.

---

## Features

- **Reliable channel discovery** — searches YouTube directly (not Google), which
  avoids CAPTCHAs and broken redirects.
- **Smart scrolling** — loads videos until the page stops growing, then stops;
  fast for small channels, complete for large ones, with a hard time budget.
- **Live progress UI** — a status console with a progress bar and an in-browser
  preview of the first rows, plus a one-click CSV download.
- **Concurrency-safe** — background jobs with per-job output files.
- **Configurable & safe by default** — headless Chrome, debugger off unless you
  opt in, all settings via environment variables.
- **Tested and CI-checked** — pytest suite and a GitHub Actions workflow.
- **Dockerized** — a single image bundles Chromium and runs under gunicorn.

---

## Requirements

- **Python 3.9+**
- **Google Chrome or Chromium** installed.
  You do **not** need to install ChromeDriver manually — Selenium 4.15+ resolves
  a matching driver automatically via Selenium Manager.

---

## Quick start (local)

```bash
git clone https://github.com/danishsyed-dev/Youtube-Content-Scraper.git
cd Youtube-Content-Scraper

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Optional: copy the sample env and set a secret key
cp .env.example .env   # then edit SECRET_KEY

python app.py
```

Open http://127.0.0.1:5000, enter a company name, and watch it work. When the
job finishes, a preview appears and the **Download CSV** button is enabled.

---

## Run with Docker

The image bundles Chromium, so nothing else is needed on the host.

```bash
docker compose up --build
# then open http://127.0.0.1:8000
```

Generated CSVs are persisted to `./output` on the host.

---

## Configuration

All configuration is via environment variables (see `.env.example`).

| Variable           | Default     | Description                                            |
|--------------------|-------------|--------------------------------------------------------|
| `SECRET_KEY`       | *(random)*  | Flask session key. Set this in production.             |
| `FLASK_DEBUG`      | `false`     | Werkzeug debugger. Keep **off** except local debugging.|
| `HOST` / `PORT`    | `127.0.0.1` / `5000` | Bind address for `python app.py`.             |
| `LOG_LEVEL`        | `INFO`      | `DEBUG`, `INFO`, `WARNING`, or `ERROR`.                |
| `OUTPUT_DIR`       | `output`    | Directory for generated CSV files.                     |
| `HEADLESS`         | `true`      | Run Chrome without a visible window.                   |
| `SCRAPE_TIMEOUT`   | `240`       | Overall time budget per scrape (seconds).              |
| `SCROLL_PAUSE`     | `1.2`       | Wait after each scroll for new videos (seconds).       |
| `SCROLL_MAX_STALE` | `3`         | No-growth scrolls before concluding we've reached the end. |
| `SCROLL_MAX_ROUNDS`| `400`       | Absolute cap on scroll iterations.                     |
| `ELEMENT_TIMEOUT`  | `20`        | Explicit-wait timeout for element lookups (seconds).   |
| `CHROME_BINARY`    | *(auto)*    | Path to a specific Chrome/Chromium binary.             |
| `MAX_COMPANY_LEN`  | `100`       | Maximum accepted length of the company input.          |

---

## HTTP API

| Method & path            | Purpose                                             |
|--------------------------|-----------------------------------------------------|
| `GET /`                  | The web UI.                                         |
| `POST /scrape`           | Start a job. Form field `company`. Returns `202` with `{"job_id"}`. |
| `GET /status/<job_id>`   | Job status, progress, and a preview of rows (JSON). |
| `GET /download/<job_id>` | The generated CSV (attachment).                     |
| `GET /health`            | Liveness probe → `{"status": "ok"}`.                |

The CSV has columns: **Link, Title, Views, Upload Time**.

---

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt

ruff check .            # lint
ruff format .           # format
pytest                  # run the test suite
```

The tests never launch a real browser — the Selenium layer is isolated behind a
pure `parse_videos()` function and an injectable scrape function.

---

## Project structure

```
app.py              Flask app factory and routes
config.py           Environment-based configuration
scraper.py          Selenium driver, channel resolution, scrolling, parsing
jobs.py             Background JobManager (threaded) + CSV writing
templates/          base.html + index.html
static/             style.css + app.js
tests/              pytest suite (routes + parser)
Dockerfile          Chromium + gunicorn image
docker-compose.yml  Local container run with persisted output
.github/            CI workflow, issue/PR templates
```

`Youtube infinite scraping.ipynb` is the original prototype notebook, kept for
reference.

---

## Disclaimer

This project is for educational purposes. Scraping must comply with the target
site's Terms of Service and `robots.txt`. Use responsibly, respect rate limits,
and don't overload YouTube's servers.

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.
