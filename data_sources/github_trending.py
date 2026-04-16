"""
Scrapes GitHub Trending page for top repositories.
Returns up to MAX_REPOS items with title, URL, description, language, stars, and daily stars.
"""

import logging
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

GITHUB_TRENDING_URL = "https://github.com/trending"
MAX_REPOS = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


@dataclass
class GithubRepo:
    title: str
    url: str
    description: str
    language: Optional[str]
    stars_total: int
    stars_today: int
    source: str = "github_trending"
    tags: list = field(default_factory=list)


def fetch(language: str = "", since: str = "daily") -> list[GithubRepo]:
    """
    Fetch GitHub trending repos.
    Args:
        language: Filter by language (e.g. "python"). Empty string = all.
        since: "daily", "weekly", or "monthly"
    Returns list of GithubRepo, empty list on failure.
    """
    url = GITHUB_TRENDING_URL
    params = {}
    if language:
        url = f"{GITHUB_TRENDING_URL}/{language}"
    if since:
        params["since"] = since

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"GitHub trending fetch failed: {e}")
        return []

    return _parse(response.text)


def _parse(html: str) -> list[GithubRepo]:
    soup = BeautifulSoup(html, "lxml")
    repos = []

    for article in soup.select("article.Box-row")[:MAX_REPOS]:
        try:
            # Title / URL
            h2 = article.select_one("h2 a")
            if not h2:
                continue
            rel_url = h2["href"].strip()
            full_url = f"https://github.com{rel_url}"
            # "owner / repo" — normalize to "owner/repo"
            title = " ".join(h2.get_text().split())

            # Description
            desc_el = article.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""

            # Language
            lang_el = article.select_one("span[itemprop='programmingLanguage']")
            language = lang_el.get_text(strip=True) if lang_el else None

            # Total stars
            stars_el = article.select("a.Link--muted")
            stars_total = 0
            if stars_el:
                raw = stars_el[0].get_text(strip=True).replace(",", "")
                stars_total = _parse_int(raw)

            # Stars today
            stars_today = 0
            today_el = article.select_one("span.d-inline-block.float-sm-right")
            if today_el:
                raw = today_el.get_text(strip=True).replace(",", "")
                stars_today = _parse_int(raw)

            repos.append(
                GithubRepo(
                    title=title,
                    url=full_url,
                    description=description,
                    language=language,
                    stars_total=stars_total,
                    stars_today=stars_today,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to parse GitHub repo entry: {e}")
            continue

    logger.info(f"GitHub trending: fetched {len(repos)} repos")
    return repos


def _parse_int(raw: str) -> int:
    """Extract leading integer from strings like '1,234 stars today'."""
    import re
    m = re.search(r"[\d,]+", raw)
    if m:
        return int(m.group().replace(",", ""))
    return 0
