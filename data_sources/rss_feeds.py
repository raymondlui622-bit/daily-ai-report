"""
Reads AI/ML news from curated RSS feeds.
Each feed can optionally be tagged with a category label.
Returns normalized FeedItem objects.
"""
from __future__ import annotations

import logging
import feedparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

MAX_PER_FEED = 5      # items pulled per feed
FETCH_WORKERS = 6
REQUEST_TIMEOUT = 15  # feedparser uses socket timeout

# (url, category_tag)
DEFAULT_FEEDS: list[tuple[str, str]] = [
    # Research / Papers
    ("https://huggingface.co/blog/feed.xml", "huggingface"),
    ("https://bair.berkeley.edu/blog/feed.xml", "research"),
    ("https://openai.com/blog/rss.xml", "openai"),
    ("https://www.anthropic.com/rss.xml", "anthropic"),
    # News / Commentary
    ("https://feeds.feedburner.com/AIWeekly", "newsletter"),
    ("https://syncedreview.com/feed/", "news"),
    ("https://venturebeat.com/category/ai/feed/", "news"),
    ("https://techcrunch.com/category/artificial-intelligence/feed/", "news"),
    # Tools / Dev
    ("https://simonwillison.net/atom/everything/", "dev"),
    ("https://www.interconnects.ai/feed", "research"),
]


@dataclass
class FeedItem:
    title: str
    url: str
    summary: str
    published: datetime
    feed_name: str
    category: str
    source: str = "rss"
    tags: list = field(default_factory=list)


def fetch(feeds: list[tuple[str, str]] | None = None) -> list[FeedItem]:
    """
    Fetch items from all configured RSS feeds.
    Args:
        feeds: List of (url, category) tuples. Uses DEFAULT_FEEDS if None.
    Returns list of FeedItem sorted by published date descending.
    """
    feeds = feeds or DEFAULT_FEEDS
    all_items: list[FeedItem] = []

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_feed, url, category): (url, category)
            for url, category in feeds
        }
        for future in as_completed(futures):
            items = future.result()
            all_items.extend(items)

    all_items.sort(key=lambda i: i.published, reverse=True)
    logger.info(f"RSS feeds: fetched {len(all_items)} items from {len(feeds)} feeds")
    return all_items


def _fetch_feed(url: str, category: str) -> list[FeedItem]:
    import socket
    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(REQUEST_TIMEOUT)
    try:
        feed = feedparser.parse(url)
        feed_name = feed.feed.get("title", url)
        items = []

        for entry in feed.entries[:MAX_PER_FEED]:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                if not title or not link:
                    continue

                summary = (
                    entry.get("summary", "")
                    or entry.get("description", "")
                    or ""
                ).strip()
                # Strip HTML tags from summary
                summary = _strip_html(summary)[:500]

                published = _parse_date(entry)

                items.append(
                    FeedItem(
                        title=title,
                        url=link,
                        summary=summary,
                        published=published,
                        feed_name=feed_name,
                        category=category,
                    )
                )
            except Exception as e:
                logger.warning(f"RSS entry parse error ({url}): {e}")
                continue

        logger.debug(f"RSS {url}: {len(items)} items")
        return items
    except Exception as e:
        logger.error(f"RSS feed failed ({url}): {e}")
        return []
    finally:
        socket.setdefaulttimeout(original_timeout)


def _parse_date(entry) -> datetime:
    """Parse published date from feedparser entry, fallback to now."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, field, None)
        if val:
            try:
                import calendar
                ts = calendar.timegm(val)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass
    return datetime.now(tz=timezone.utc)


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    from bs4 import BeautifulSoup
    return BeautifulSoup(text, "lxml").get_text(separator=" ").strip()
