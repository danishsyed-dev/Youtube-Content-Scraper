"""Tests for the Flask routes and end-to-end job lifecycle (no browser)."""

from __future__ import annotations

from conftest import make_fake_scrape
from scraper import ScraperError


def test_index_serves_page(make_client):
    client, _ = make_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Channel video extractor" in resp.data


def test_health(make_client):
    client, _ = make_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_scrape_requires_company(make_client):
    client, _ = make_client()
    resp = client.post("/scrape", data={"company": "   "})
    assert resp.status_code == 400
    assert "enter a company" in resp.get_json()["error"].lower()


def test_scrape_rejects_overlong_name(make_client):
    client, _ = make_client()
    resp = client.post("/scrape", data={"company": "x" * 200})
    assert resp.status_code == 400
    assert "too long" in resp.get_json()["error"].lower()


def test_full_lifecycle_success(make_client):
    client, _ = make_client()
    # Submit
    resp = client.post("/scrape", data={"company": "Figma"})
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]

    # Status (job ran synchronously, so it's already done)
    status = client.get(f"/status/{job_id}")
    assert status.status_code == 200
    body = status.get_json()
    assert body["status"] == "done"
    assert body["row_count"] == 2
    assert body["download_ready"] is True
    assert len(body["preview"]) == 2
    assert "Figma" in body["preview"][0]["title"]

    # Download
    dl = client.get(f"/download/{job_id}")
    assert dl.status_code == 200
    assert dl.mimetype == "text/csv"
    assert b"Link,Title,Views,Upload Time" in dl.data
    assert b"Figma video one" in dl.data
    assert "attachment" in dl.headers["Content-Disposition"]
    assert "Figma_videos.csv" in dl.headers["Content-Disposition"]


def test_status_unknown_job_404(make_client):
    client, _ = make_client()
    resp = client.get("/status/does-not-exist")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_download_unknown_job_404(make_client):
    client, _ = make_client()
    resp = client.get("/download/nope")
    assert resp.status_code == 404


def test_scrape_error_surfaces_to_status(make_client):
    client, _ = make_client(
        scrape_fn=make_fake_scrape(error=ScraperError("channel not found"))
    )
    resp = client.post("/scrape", data={"company": "Nonexistent"})
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]

    status = client.get(f"/status/{job_id}").get_json()
    assert status["status"] == "error"
    assert "channel not found" in status["error"]
    assert status["download_ready"] is False


def test_unexpected_error_is_caught(make_client):
    def boom(company_name, *, progress=None, **kwargs):
        raise RuntimeError("kaboom")

    client, _ = make_client(scrape_fn=boom)
    resp = client.post("/scrape", data={"company": "X"})
    job_id = resp.get_json()["job_id"]
    status = client.get(f"/status/{job_id}").get_json()
    assert status["status"] == "error"
    assert "unexpected error" in status["error"].lower()


def test_download_before_ready_conflict(config):
    # A running job with no CSV yet must not be downloadable.
    from jobs import Job, JobManager, JobStatus

    from app import create_app

    jm = JobManager(output_dir=config.OUTPUT_DIR, scrape_fn=make_fake_scrape())
    app = create_app(config=config, job_manager=jm)
    client = app.test_client()

    job = Job(id="manual123", company="Pending Co", status=JobStatus.RUNNING)
    jm._jobs[job.id] = job  # noqa: SLF001 - deliberate for the test

    resp = client.get(f"/download/{job.id}")
    assert resp.status_code == 409
