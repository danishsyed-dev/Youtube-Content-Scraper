"""Tests for the pure HTML parser (no browser required)."""

from __future__ import annotations

from scraper import Video, parse_videos, videos_to_dicts

# A trimmed but structurally faithful snippet of a YouTube "Videos" tab.
SAMPLE_HTML = """
<div id="contents">
  <ytd-rich-item-renderer>
    <div id="dismissible">
      <a id="video-title-link" href="/watch?v=aaa111"
         title="First Video — Full Title" aria-label="First Video by Chan">
        <yt-formatted-string id="video-title">First Video</yt-formatted-string>
      </a>
      <div id="metadata-line">
        <span class="inline-metadata-item style-scope ytd-video-meta-block">12K views</span>
        <span class="inline-metadata-item style-scope ytd-video-meta-block">3 days ago</span>
      </div>
    </div>
  </ytd-rich-item-renderer>

  <ytd-rich-item-renderer>
    <div id="dismissible">
      <a id="video-title-link" href="/watch?v=bbb222" title="Second Video">
        <yt-formatted-string id="video-title">Second Video</yt-formatted-string>
      </a>
      <div id="metadata-line">
        <span class="inline-metadata-item">4.5M views</span>
        <span class="inline-metadata-item">1 year ago</span>
      </div>
    </div>
  </ytd-rich-item-renderer>

  <!-- Duplicate of the first item — should be de-duplicated by link. -->
  <ytd-rich-item-renderer>
    <div id="dismissible">
      <a id="video-title-link" href="/watch?v=aaa111" title="First Video — Full Title">
      </a>
    </div>
  </ytd-rich-item-renderer>
</div>
"""


def test_parse_extracts_rows():
    videos = parse_videos(SAMPLE_HTML)
    # Two unique videos (the third is a duplicate link).
    assert len(videos) == 2


def test_parse_fields_and_absolute_links():
    videos = parse_videos(SAMPLE_HTML)
    first = videos[0]
    assert isinstance(first, Video)
    assert first.link == "https://www.youtube.com/watch?v=aaa111"
    # Prefers the full title attribute over the visible text.
    assert first.title == "First Video — Full Title"
    assert first.views == "12K views"
    assert first.upload_time == "3 days ago"


def test_parse_second_row_metadata_without_style_scope_class():
    videos = parse_videos(SAMPLE_HTML)
    second = videos[1]
    assert second.link.endswith("bbb222")
    assert second.views == "4.5M views"
    assert second.upload_time == "1 year ago"


def test_parse_handles_missing_metadata_gracefully():
    html = """
    <ytd-rich-item-renderer>
      <a id="video-title-link" href="/watch?v=zzz999" title="No Meta"></a>
    </ytd-rich-item-renderer>
    """
    videos = parse_videos(html)
    assert len(videos) == 1
    assert videos[0].views == ""
    assert videos[0].upload_time == ""
    assert videos[0].title == "No Meta"


def test_parse_skips_items_without_anchor():
    html = "<ytd-rich-item-renderer><div>nothing useful</div></ytd-rich-item-renderer>"
    assert parse_videos(html) == []


def test_parse_empty_html():
    assert parse_videos("") == []


def test_parse_falls_back_to_video_title_id():
    # Some layouts use id="video-title" instead of "video-title-link".
    html = """
    <ytd-rich-item-renderer>
      <a id="video-title" href="/watch?v=ccc333" title="Legacy Layout"></a>
    </ytd-rich-item-renderer>
    """
    videos = parse_videos(html)
    assert len(videos) == 1
    assert videos[0].link.endswith("ccc333")
    assert videos[0].title == "Legacy Layout"


def test_parse_current_rich_grid_layout():
    html = """
    <ytd-rich-grid-media>
      <a class="yt-simple-endpoint focus-on-expand style-scope ytd-rich-grid-media"
         href="/watch?v=grid123" title="Grid Video"></a>
      <span class="inline-metadata-item">99 views</span>
      <span class="inline-metadata-item">2 hours ago</span>
    </ytd-rich-grid-media>
    """
    videos = parse_videos(html)
    assert len(videos) == 1
    assert videos[0].link.endswith("grid123")
    assert videos[0].title == "Grid Video"
    assert videos[0].views == "99 views"
    assert videos[0].upload_time == "2 hours ago"


def test_videos_to_dicts_shape():
    videos = parse_videos(SAMPLE_HTML)
    dicts = videos_to_dicts(videos)
    assert set(dicts[0].keys()) == {"link", "title", "views", "upload_time"}


def test_to_videos_url_normalization():
    from scraper import _to_videos_url

    assert _to_videos_url("/@figma") == "https://www.youtube.com/@figma/videos"
    assert _to_videos_url("/@figma/featured") == "https://www.youtube.com/@figma/videos"
    assert (
        _to_videos_url("https://www.youtube.com/channel/abc/streams?x=1")
        == "https://www.youtube.com/channel/abc/videos"
    )
    assert _to_videos_url("/@figma/videos/") == "https://www.youtube.com/@figma/videos"
