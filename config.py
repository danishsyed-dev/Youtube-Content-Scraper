"""Application configuration.

All settings are read from environment variables so the app can be configured
without code changes. Sensible, safe-by-default values are used when a variable
is not set (for example, the Werkzeug debugger is OFF unless explicitly enabled).
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    """Interpret common truthy/falsy strings from the environment."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class Config:
    """Central configuration object.

    Instantiated once at startup (see ``app.create_app``). Reading everything in
    ``__init__`` means tests can set environment variables and build a fresh
    ``Config`` to exercise different settings.
    """

    def __init__(self) -> None:
        # --- Flask ---
        # SECRET_KEY is required for session security in production. We fall back
        # to a random key in development so the app still runs, but log a warning
        # (see app.create_app) because sessions won't survive a restart.
        self.SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
        self.DEBUG: bool = _env_bool("FLASK_DEBUG", default=False)
        self.HOST: str = os.environ.get("HOST", "127.0.0.1")
        self.PORT: int = _env_int("PORT", 5000)

        # --- Logging ---
        self.LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

        # --- Output ---
        # Where generated CSV files are written. Each job gets a unique filename,
        # so concurrent users never overwrite one another.
        self.OUTPUT_DIR: Path = Path(
            os.environ.get("OUTPUT_DIR", Path.cwd() / "output")
        ).resolve()

        # --- Selenium / scraping ---
        self.HEADLESS: bool = _env_bool("HEADLESS", default=True)
        # Overall wall-clock budget for a single scrape, in seconds.
        self.SCRAPE_TIMEOUT: int = _env_int("SCRAPE_TIMEOUT", 240)
        # Scroll tuning for the "scroll until the page stops growing" loop.
        self.SCROLL_PAUSE: float = _env_float("SCROLL_PAUSE", 1.2)
        # How many consecutive scrolls with no new content before we stop.
        self.SCROLL_MAX_STALE: int = _env_int("SCROLL_MAX_STALE", 3)
        # Hard cap on scroll iterations as a final safety net.
        self.SCROLL_MAX_ROUNDS: int = _env_int("SCROLL_MAX_ROUNDS", 400)
        # Explicit-wait timeout for individual element lookups.
        self.ELEMENT_TIMEOUT: int = _env_int("ELEMENT_TIMEOUT", 20)
        # Optional: point at a specific Chrome/Chromium binary (useful in Docker).
        self.CHROME_BINARY: str = os.environ.get("CHROME_BINARY", "")
        # Max company-name length we accept from the form.
        self.MAX_COMPANY_LEN: int = _env_int("MAX_COMPANY_LEN", 100)

    def ensure_output_dir(self) -> Path:
        """Create the output directory if it doesn't exist and return it."""
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return self.OUTPUT_DIR
