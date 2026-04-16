"""
Deduplicates items across sources by URL and title similarity.
URL dedup is exact (normalized). Title dedup uses token overlap ratio.
"""

import re
from urllib.parse import urlparse, urlunparse


def deduplicate(items: list) -> list:
    """
    Remove duplicate items from a mixed list of dataclass objects.
    Each item must have a .url and .title attribute.
    Returns deduplicated list preserving original order.
    """
    seen_urls: set[str] = set()
    seen_title_tokens: list[set[str]] = []
    result = []

    for item in items:
        norm_url = _normalize_url(item.url)
        if norm_url in seen_urls:
            continue

        title_tokens = _tokenize(item.title)
        if _is_duplicate_title(title_tokens, seen_title_tokens):
            continue

        seen_urls.add(norm_url)
        seen_title_tokens.append(title_tokens)
        result.append(item)

    return result


def _normalize_url(url: str) -> str:
    """Strip tracking params and normalize URL for comparison."""
    try:
        parsed = urlparse(url.strip().lower())
        # Drop fragment and common tracking query params
        clean = parsed._replace(fragment="", query="")
        return urlunparse(clean).rstrip("/")
    except Exception:
        return url.strip().lower()


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens, removing stopwords and short tokens."""
    stopwords = {"a", "an", "the", "and", "or", "of", "in", "to", "for",
                 "with", "on", "at", "by", "from", "is", "it", "as", "be"}
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if len(t) > 2 and t not in stopwords}


def _is_duplicate_title(tokens: set[str], seen: list[set[str]], threshold: float = 0.75) -> bool:
    """Return True if tokens overlap >= threshold with any seen title."""
    if not tokens:
        return False
    for seen_tokens in seen:
        if not seen_tokens:
            continue
        intersection = len(tokens & seen_tokens)
        union = len(tokens | seen_tokens)
        if union > 0 and intersection / union >= threshold:
            return True
    return False
