"""YouTube channel video scraper.

The heavy lifting is split into small pieces so the fragile, browser-dependent
parts are isolated from the pure logic that can be unit-tested without a browser:

* ``parse_videos(html)`` — pure function: HTML in, list of ``Video`` out.
* ``build_driver(...)`` — constructs a configured Selenium Chrome driver.
* ``scrape_channel(...)`` — orchestrates: resolve channel, scroll, parse.

Channel resolution uses YouTube's own search results page rather than scraping
Google, which avoids Google CAPTCHAs and is considerably more stable.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import Callable, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Progress callback: (fraction_complete_0_to_1, human_readable_message)
ProgressCallback = Callable[[float, str], None]


class ScraperError(Exception):
    """Raised for any expected, user-facing scraping failure.

    Distinct from unexpected exceptions so the web layer can show a clean
    message for these while treating everything else as an internal error.
    """


@dataclass
class Video:
    """A single scraped video row."""

    link: str
    title: str
    views: str
    upload_time: str


# --------------------------------------------------------------------------- #
# Pure parsing (no browser required — unit-testable)
# --------------------------------------------------------------------------- #

def _clean(text: Optional[str]) -> str:
    return (text or "").strip()


def parse_videos(html: str) -> list[Video]:
    """Extract videos from a YouTube channel "Videos" tab page source.

    Resilient to missing fields: a video with no parseable metadata still
    yields a row (with blank fields) rather than being silently dropped, and
    malformed items never raise. Deduplicates by link, preserving order.
    """
    soup = BeautifulSoup(html, "html.parser")
    videos: list[Video] = []
    seen: set[str] = set()

    for item in soup.find_all("ytd-rich-item-renderer"):
        # The title anchor carries both the href and (usually) the full title.
        # YouTube has shipped both "video-title-link" and "video-title" as the
        # id over time, so try both.
        anchor = item.find("a", id="video-title-link") or item.find(
            "a", id="video-title"
        )
        if anchor is None or not anchor.get("href"):
            continue

        href = anchor["href"]
        link = urljoin("https://www.youtube.com", href)

        # Prefer the title attribute (full, untruncated); fall back to the
        # visible text, then to an aria-label.
        title = _clean(anchor.get("title")) or _clean(anchor.get_text())
        if not title:
            title = _clean(anchor.get("aria-label"))

        # Metadata line holds "N views" and "X ago" as separate spans.
        meta_spans = item.find_all("span", class_="inline-metadata-item")
        views = _clean(meta_spans[0].get_text()) if len(meta_spans) >= 1 else ""
        upload_time = _clean(meta_spans[1].get_text()) if len(meta_spans) >= 2 else ""

        if link in seen:
            continue
        seen.add(link)
        videos.append(Video(link=link, title=title, views=views, upload_time=upload_time))

    return videos


def videos_to_dicts(videos: list[Video]) -> list[dict]:
    """Convert Video objects to plain dicts (for JSON/CSV/DataFrame)."""
    return [asdict(v) for v in videos]


# --------------------------------------------------------------------------- #
# Selenium driver
# --------------------------------------------------------------------------- #

def build_driver(headless: bool = True, chrome_binary: str = ""):
    """Create a configured Chrome WebDriver.

    Selenium 4.10+ ships Selenium Manager, which downloads a matching driver
    automatically — no manual ChromeDriver install or PATH setup required.
    """
    # Imported lazily so importing this module (e.g. for parse_videos in tests)
    # doesn't require Selenium to be installed or a browser to be present.
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    # Flags that make Chrome behave in containers / CI and reduce noise.
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
    options.add_argument("--mute-audio")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    if chrome_binary:
        options.binary_location = chrome_binary

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:  # noqa: BLE001 - surface a clean, actionable message
        raise ScraperError(
            "Could not start Chrome. Make sure Google Chrome or Chromium is "
            "installed and reachable. Original error: " + str(exc)
        ) from exc

    driver.set_page_load_timeout(60)
    return driver


def _dismiss_consent(driver) -> None:
    """Best-effort click-through of YouTube's cookie-consent interstitial.

    Only appears in some regions; failures here are non-fatal.
    """
    from selenium.webdriver.common.by import By

    selectors = [
        "//button[.//span[contains(., 'Accept all')]]",
        "//button[.//span[contains(., 'Accept the use')]]",
        "//button[contains(., 'Accept all')]",
        "//button[@aria-label='Accept all']",
        "//tp-yt-paper-button[contains(., 'Accept all')]",
    ]
    for xpath in selectors:
        try:
            buttons = driver.find_elements(By.XPATH, xpath)
            if buttons:
                buttons[0].click()
                time.sleep(1.0)
                logger.debug("Dismissed consent dialog via %s", xpath)
                return
        except Exception:  # noqa: BLE001 - consent handling is best-effort
            continue


# --------------------------------------------------------------------------- #
# Channel resolution
# --------------------------------------------------------------------------- #

def resolve_channel_url(driver, company_name: str, element_timeout: int) -> str:
    """Find the most relevant channel's "Videos" page for a company name.

    Uses YouTube's own search results and picks the first channel renderer.
    Falls back to the first video's owner if no channel renderer is present.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    search_url = "https://www.youtube.com/results?search_query=" + quote_plus(company_name)
    logger.info("Searching YouTube for channel: %s", company_name)
    driver.get(search_url)
    _dismiss_consent(driver)

    try:
        WebDriverWait(driver, element_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-item-section-renderer"))
        )
    except Exception as exc:  # noqa: BLE001
        raise ScraperError(
            "YouTube search results did not load in time. This can happen if "
            "YouTube served a CAPTCHA or the network is slow."
        ) from exc

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Preferred: an explicit channel result.
    channel = soup.find("ytd-channel-renderer")
    if channel is not None:
        link = channel.find("a", href=True)
        if link and link["href"]:
            return _to_videos_url(link["href"])

    # Fallback: the owner/byline of the first video result.
    byline = soup.select_one("ytd-video-renderer ytd-channel-name a[href]")
    if byline and byline.get("href"):
        return _to_videos_url(byline["href"])

    raise ScraperError(
        f"Could not find a YouTube channel for '{company_name}'. "
        "Try a more specific name."
    )


def _to_videos_url(href: str) -> str:
    """Normalize a channel href into its "/videos" tab absolute URL."""
    url = urljoin("https://www.youtube.com", href).split("?")[0].rstrip("/")
    # Strip a trailing tab segment if present, then append /videos.
    for tab in ("/videos", "/featured", "/streams", "/shorts", "/playlists", "/community"):
        if url.endswith(tab):
            url = url[: -len(tab)]
            break
    return url + "/videos"


# --------------------------------------------------------------------------- #
# Scrolling
# --------------------------------------------------------------------------- #

def _scroll_until_stable(
    driver,
    *,
    pause: float,
    max_stale: int,
    max_rounds: int,
    deadline: float,
    progress: Optional[ProgressCallback],
) -> None:
    """Scroll to the bottom repeatedly until the page height stops growing.

    Stops when height is unchanged for ``max_stale`` consecutive rounds, when
    ``max_rounds`` is hit, or when the overall ``deadline`` passes.
    """
    last_height = 0
    stale = 0
    for round_num in range(max_rounds):
        if time.monotonic() > deadline:
            logger.warning("Scroll stopped: overall scrape timeout reached.")
            break

        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.documentElement.scrollHeight;")

        if new_height <= last_height:
            stale += 1
            if stale >= max_stale:
                logger.info("Reached end of channel after %d scrolls.", round_num + 1)
                break
        else:
            stale = 0
        last_height = new_height

        if progress is not None:
            # We can't know the true total, so report a soft progress signal
            # that eases toward ~0.85 during scrolling.
            frac = min(0.85, 0.15 + 0.7 * (round_num + 1) / max_rounds)
            progress(frac, f"Loading videos… (scroll {round_num + 1})")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def scrape_channel(
    company_name: str,
    *,
    headless: bool = True,
    chrome_binary: str = "",
    scrape_timeout: int = 240,
    scroll_pause: float = 1.2,
    scroll_max_stale: int = 3,
    scroll_max_rounds: int = 400,
    element_timeout: int = 20,
    progress: Optional[ProgressCallback] = None,
) -> list[Video]:
    """Full scrape: resolve the channel, load all videos, and parse them.

    Returns a list of ``Video``. Raises ``ScraperError`` for expected failures
    (channel not found, browser missing, timeouts) with user-friendly messages.
    """
    company_name = (company_name or "").strip()
    if not company_name:
        raise ScraperError("Please enter a company name.")

    def report(frac: float, msg: str) -> None:
        if progress is not None:
            progress(frac, msg)

    deadline = time.monotonic() + scrape_timeout
    report(0.05, "Starting browser…")
    driver = build_driver(headless=headless, chrome_binary=chrome_binary)
    try:
        report(0.1, "Finding channel…")
        videos_url = resolve_channel_url(driver, company_name, element_timeout)
        logger.info("Resolved channel videos URL: %s", videos_url)

        report(0.15, "Opening channel…")
        driver.get(videos_url)
        _dismiss_consent(driver)

        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            WebDriverWait(driver, element_timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "ytd-rich-item-renderer")
                )
            )
        except Exception:  # noqa: BLE001
            # No videos rendered — could be an empty channel. Parse anyway;
            # we may simply return zero rows.
            logger.warning("No video items detected before timeout for %s", company_name)

        _scroll_until_stable(
            driver,
            pause=scroll_pause,
            max_stale=scroll_max_stale,
            max_rounds=scroll_max_rounds,
            deadline=deadline,
            progress=progress,
        )

        report(0.9, "Extracting video data…")
        videos = parse_videos(driver.page_source)
        logger.info("Scraped %d videos for '%s'", len(videos), company_name)

        if not videos:
            raise ScraperError(
                f"No videos were found for '{company_name}'. The channel may be "
                "empty, or YouTube's layout may have changed."
            )

        report(1.0, f"Done — {len(videos)} videos.")
        return videos
    finally:
        try:
            driver.quit()
        except Exception:  # noqa: BLE001 - never mask the real error on cleanup
            logger.debug("Error while quitting driver", exc_info=True)
