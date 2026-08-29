"""Background job management for scrape requests.

Scraping a channel takes minutes, so it must not run inside the HTTP request.
``JobManager`` runs each scrape on a worker thread and tracks its state, so the
browser can poll ``/status/<job_id>`` and download the CSV when it's ready.

Each job writes to a unique CSV file, so concurrent users never collide.

State is intentionally in-memory: this app is single-process and jobs are
ephemeral. For a multi-worker deployment you'd swap this for Redis/DB-backed
storage, but that would be over-engineering here.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from scraper import ScraperError, Video, videos_to_dicts

logger = logging.getLogger(__name__)

CSV_COLUMNS = ["link", "title", "views", "upload_time"]
CSV_HEADERS = ["Link", "Title", "Views", "Upload Time"]

# A scrape function with the same signature as scraper.scrape_channel.
# Injected so tests can supply a fake and avoid launching a browser.
ScrapeFn = Callable[..., list[Video]]


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class Job:
    id: str
    company: str
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    message: str = "Queued"
    error: Optional[str] = None
    csv_path: Optional[Path] = None
    row_count: int = 0
    preview: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_public_dict(self) -> dict:
        """Serialize the fields safe to expose over the API."""
        return {
            "id": self.id,
            "company": self.company,
            "status": self.status.value,
            "progress": round(self.progress, 3),
            "message": self.message,
            "error": self.error,
            "row_count": self.row_count,
            "preview": self.preview,
            "download_ready": self.status == JobStatus.DONE,
        }


class JobManager:
    """Creates, runs, and tracks scrape jobs."""

    def __init__(
        self,
        output_dir: Path,
        scrape_fn: ScrapeFn,
        scrape_kwargs: Optional[dict] = None,
        *,
        preview_rows: int = 25,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._scrape_fn = scrape_fn
        self._scrape_kwargs = scrape_kwargs or {}
        self._preview_rows = preview_rows
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def submit(self, company: str, *, synchronous: bool = False) -> Job:
        """Create a job and start it. If ``synchronous`` (tests), run inline."""
        job_id = uuid.uuid4().hex
        job = Job(id=job_id, company=company)
        with self._lock:
            self._jobs[job_id] = job

        if synchronous:
            self._run(job)
        else:
            thread = threading.Thread(
                target=self._run, args=(job,), name=f"scrape-{job_id[:8]}", daemon=True
            )
            thread.start()
        return job

    def _run(self, job: Job) -> None:
        """Worker body: run the scrape, write CSV, update job state."""

        def progress(frac: float, msg: str) -> None:
            with self._lock:
                job.progress = frac
                job.message = msg

        with self._lock:
            job.status = JobStatus.RUNNING
            job.message = "Starting…"

        try:
            videos = self._scrape_fn(
                job.company, progress=progress, **self._scrape_kwargs
            )
            rows = videos_to_dicts(videos)
            csv_path = self._output_dir / f"{job.id}.csv"
            df = pd.DataFrame(rows, columns=CSV_COLUMNS)
            df.to_csv(csv_path, index=False, header=CSV_HEADERS)

            with self._lock:
                job.csv_path = csv_path
                job.row_count = len(rows)
                job.preview = rows[: self._preview_rows]
                job.status = JobStatus.DONE
                job.progress = 1.0
                job.message = f"Completed — {len(rows)} videos."
            logger.info("Job %s completed with %d rows", job.id, len(rows))
        except ScraperError as exc:
            self._fail(job, str(exc))
        except Exception as exc:  # noqa: BLE001 - catch-all so a thread never dies silently
            logger.exception("Unexpected error in job %s", job.id)
            self._fail(job, f"Unexpected error: {exc}")

    def _fail(self, job: Job, message: str) -> None:
        with self._lock:
            job.status = JobStatus.ERROR
            job.error = message
            job.message = message
        logger.warning("Job %s failed: %s", job.id, message)
