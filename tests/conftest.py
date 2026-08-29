"""Shared pytest fixtures.

Tests never launch a real browser. Instead we inject a fake scrape function
into the JobManager and run jobs synchronously, so the whole HTTP surface and
job lifecycle are exercised deterministically and fast.
"""

from __future__ import annotations

import pytest

from config import Config
from jobs import JobManager
from scraper import ScraperError, Video


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    return Config()


def make_fake_scrape(videos=None, error=None):
    """Build a scrape_fn stand-in matching scraper.scrape_channel's signature."""

    def _fake(company_name, *, progress=None, **kwargs):
        if progress:
            progress(0.5, "halfway")
        if error:
            raise error
        if videos is not None:
            return list(videos)
        # Default: two deterministic rows derived from the query.
        return [
            Video(
                link=f"https://www.youtube.com/watch?v={company_name}-1",
                title=f"{company_name} video one",
                views="1.2K views",
                upload_time="2 days ago",
            ),
            Video(
                link=f"https://www.youtube.com/watch?v={company_name}-2",
                title=f"{company_name} video two",
                views="900 views",
                upload_time="1 week ago",
            ),
        ]

    return _fake


@pytest.fixture
def make_client(config):
    """Factory: build a test client whose JobManager runs jobs synchronously."""
    from app import create_app

    def _make(scrape_fn=None):
        if scrape_fn is None:
            scrape_fn = make_fake_scrape()

        class SyncJobManager(JobManager):
            def submit(self, company, *, synchronous=False):
                return super().submit(company, synchronous=True)

        jm = SyncJobManager(output_dir=config.OUTPUT_DIR, scrape_fn=scrape_fn)
        app = create_app(config=config, job_manager=jm)
        app.config.update(TESTING=True)
        return app.test_client(), jm

    return _make


@pytest.fixture
def scraper_error():
    return ScraperError
