"""
Scores and ranks items from all sources into a unified top-N list.
Each source type uses its own scoring heuristic, then items compete globally.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class RankedItem:
    item: Any          # original dataclass (GithubRepo | HNStory | FeedItem)
    score: float
    source: str
    section: str       # "github" | "hackernews" | "rss"


def rank(
    github_items: list,
    hn_items: list,
    rss_items: list,
    top_n: int = 20,
) -> list[RankedItem]:
    """
    Score items from each source and return a unified ranked list.
    """
    ranked: list[RankedItem] = []

    for item in github_items:
        ranked.append(RankedItem(
            item=item,
            score=_score_github(item),
            source="github_trending",
            section="github",
        ))

    for item in hn_items:
        ranked.append(RankedItem(
            item=item,
            score=_score_hn(item),
            source="hackernews",
            section="hackernews",
        ))

    for item in rss_items:
        ranked.append(RankedItem(
            item=item,
            score=_score_rss(item),
            source="rss",
            section="rss",
        ))

    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked[:top_n]


def rank_by_section(
    github_items: list,
    hn_items: list,
    rss_items: list,
    github_top: int = 5,
    hn_top: int = 8,
    rss_top: int = 8,
) -> dict[str, list[RankedItem]]:
    """
    Rank each section independently and return a dict keyed by section.
    Better for preserving source diversity in the final report.
    """
    github_ranked = sorted(
        [RankedItem(item=i, score=_score_github(i), source="github_trending", section="github")
         for i in github_items],
        key=lambda r: r.score, reverse=True
    )[:github_top]

    hn_ranked = sorted(
        [RankedItem(item=i, score=_score_hn(i), source="hackernews", section="hackernews")
         for i in hn_items],
        key=lambda r: r.score, reverse=True
    )[:hn_top]

    rss_ranked = sorted(
        [RankedItem(item=i, score=_score_rss(i), source="rss", section="rss")
         for i in rss_items],
        key=lambda r: r.score, reverse=True
    )[:rss_top]

    return {
        "github": github_ranked,
        "hackernews": hn_ranked,
        "rss": rss_ranked,
    }


# --- Scoring heuristics ---

def _score_github(item) -> float:
    """
    Weight: stars_today (primary) + log of total stars.
    Stars today indicates recent momentum.
    """
    import math
    today_weight = item.stars_today * 3.0
    total_weight = math.log1p(item.stars_total) * 10
    return today_weight + total_weight


def _score_hn(item) -> float:
    """
    Weight: score (upvotes) + comment signal (engagement).
    Comments indicate active discussion.
    """
    return item.score * 1.0 + item.comments * 0.5


def _score_rss(item) -> float:
    """
    Weight: recency (hours since published).
    Newer articles score higher. Cap at 48h window.
    """
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc)
    age_hours = (now - item.published).total_seconds() / 3600
    # Score decays linearly from 48 down to 0 over 48 hours
    return max(0.0, 48.0 - age_hours)
