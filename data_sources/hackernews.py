"""
Fetches top Hacker News stories via the official Firebase API.
Filters for AI/ML relevance by default; returns full metadata including score and comment count.
"""
from __future__ import annotations

import logging
import re
import requests
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

HN_TOP_STORIES_URL = "https://hacker-news.firebase.google.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebase.google.com/v0/item/{id}.json"
HN_STORY_URL = "https://news.ycombinator.com/item?id={id}"

MAX_CANDIDATES = 60   # top N story IDs to consider
MAX_RESULTS = 15      # stories returned after filtering
FETCH_WORKERS = 10    # parallel item fetches
REQUEST_TIMEOUT = 10

# Keywords for AI relevance filtering (case-insensitive)
AI_KEYWORDS = re.compile(
    r"\b(ai|ml|llm|gpt|claude|gemini|mistral|llama|neural|transformer|"
    r"machine.?learning|deep.?learning|language.?model|artificial.?intel|"
    r"openai|anthropic|hugging.?face|diffusion|inference|fine.?tun|"
    r"embeddings?|rag|vector|agent|autonomous|robotics?|nlp|computer.?vision|"
    r"benchmark|eval|alignment|safety|rlhf|multimodal|foundation.?model)\b",
    re.IGNORECASE,
)


@dataclass
class HNStory:
    id: int
    title: str
    url: str
    hn_url: str
    score: int
    comments: int
    author: str
    source: str = "hackernews"
    tags: list = field(default_factory=list)


def fetch(ai_only: bool = True) -> list[HNStory]:
    """
    Fetch top HN stories.
    Args:
        ai_only: If True, filter to AI/ML-relevant stories only.
    Returns list of HNStory, empty list on failure.
    """
    try:
        resp = requests.get(HN_TOP_STORIES_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        ids = resp.json()[:MAX_CANDIDATES]
    except Exception as e:
        logger.error(f"HN top stories fetch failed: {e}")
        return []

    stories = _fetch_items(ids)

    if ai_only:
        stories = [s for s in stories if _is_ai_relevant(s)]

    # Sort by score descending, cap results
    stories.sort(key=lambda s: s.score, reverse=True)
    result = stories[:MAX_RESULTS]
    logger.info(f"HN: fetched {len(result)} stories (ai_only={ai_only})")
    return result


def _fetch_items(ids: list[int]) -> list[HNStory]:
    stories = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
        futures = {executor.submit(_fetch_item, id_): id_ for id_ in ids}
        for future in as_completed(futures):
            story = future.result()
            if story:
                stories.append(story)
    return stories


def _fetch_item(story_id: int) -> HNStory | None:
    try:
        resp = requests.get(
            HN_ITEM_URL.format(id=story_id), timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()

        if not data or data.get("type") != "story" or data.get("dead") or data.get("deleted"):
            return None

        return HNStory(
            id=story_id,
            title=data.get("title", ""),
            url=data.get("url", HN_STORY_URL.format(id=story_id)),
            hn_url=HN_STORY_URL.format(id=story_id),
            score=data.get("score", 0),
            comments=data.get("descendants", 0),
            author=data.get("by", ""),
        )
    except Exception as e:
        logger.warning(f"HN item {story_id} fetch failed: {e}")
        return None


def _is_ai_relevant(story: HNStory) -> bool:
    return bool(AI_KEYWORDS.search(story.title) or AI_KEYWORDS.search(story.url))
