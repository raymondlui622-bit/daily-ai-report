"""
Claude-powered summarization layer.
- Generates a 2-sentence summary per item
- Adds an operator insight: practical "so what" for someone following AI/tech
- Produces a top-level briefing intro paragraph for the full report
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS_PER_ITEM = 450
MAX_TOKENS_BRIEFING = 500


DISPLAY_SECTIONS = ["money_moves", "platforms", "systems", "distribution", "signals"]


@dataclass
class SummarizedItem:
    title: str
    url: str
    display_section: str   # money_moves | platforms | systems | distribution | signals
    what: str              # plain-English explanation
    why: str               # trend signal / why it matters now
    how_to_use: str        # practical application for a non-technical operator
    action: str            # one specific actionable idea
    source: str
    section: str           # original data source: github | hackernews | rss
    original: object


def summarize_items(ranked_items: list, operator_context: str = "") -> list[SummarizedItem]:
    """
    Summarize a list of RankedItem objects using Claude.
    Processes items one at a time to keep context focused.
    Items that fail summarization are included with their raw title/description.
    """
    client = _get_client()
    results = []

    for ranked in ranked_items:
        try:
            summarized = _summarize_one(client, ranked, operator_context)
            results.append(summarized)
        except Exception as e:
            logger.warning(f"Summarization failed for '{ranked.item.title}': {e}")
            results.append(_fallback(ranked))

    return results


def generate_briefing_intro(
    summarized_items: list[SummarizedItem],
    date_str: str,
    operator_context: str = "",
) -> str:
    """
    Generate a short intro paragraph for the full report.
    Synthesizes the day's top themes into 3-4 sentences.
    Returns empty string on failure.
    """
    client = _get_client()
    if client is None:
        return ""

    titles = [f"- {s.title}" for s in summarized_items[:15]]
    titles_str = "\n".join(titles)

    context_line = f"\nOperator context: {operator_context}" if operator_context else ""

    prompt = f"""You are writing a morning briefing for a non-technical entrepreneur who wants to find opportunities in AI.

Today's stories:{context_line}

{titles_str}

Identify 2-3 top opportunity themes from today's stories. For each theme, write a bold header and 2-3 bullets focused on money, automation, or advantage.
Plain English only. No jargon. Be specific and actionable.

Use exactly this format (no intro, no conclusion):

**[OPPORTUNITY THEME IN CAPS]**
- [specific opportunity or insight, 1 sentence]
- [specific opportunity or insight, 1 sentence]

**[OPPORTUNITY THEME IN CAPS]**
- [specific opportunity or insight, 1 sentence]
- [specific opportunity or insight, 1 sentence]"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_BRIEFING,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Briefing intro generation failed: {e}")
        return ""


def _summarize_one(client, ranked, operator_context: str) -> "SummarizedItem":
    item = ranked.item
    source_context = _build_source_context(item, ranked.section)

    context_line = f"\nOperator context: {operator_context}" if operator_context else ""

    prompt = f"""You are writing a daily briefing for a non-technical entrepreneur who wants to find opportunities in AI — ways to make money, automate their business, or spot trends early. No jargon. No theory. Just practical, plain-English insights.{context_line}

Item details:
Title: {item.title}
Source: {ranked.source}
{source_context}

First, classify this item into exactly ONE of these sections:
- money_moves: Direct opportunities to make money, save time, or offer a service
- platforms: Tools or companies making AI easier for non-coders (gaining traction)
- systems: Workflows, automations, or business models worth copying
- distribution: Content strategies, hooks, or formats getting attention
- signals: Early-stage tools, repos, or patterns before they go mainstream

Then respond with exactly this format (no extra text, no preamble):

SECTION: [money_moves | platforms | systems | distribution | signals]
WHAT: [1 sentence. What this is, in plain English. Imagine explaining to a smart friend who doesn't code.]
WHY: [1 sentence. Why this is gaining traction or matters right now — the trend signal.]
HOW: [1 sentence. How a non-technical entrepreneur could practically use or benefit from this today.]
ACTION: [1 sentence. One specific thing they could do this week to test, build, or profit from this — be concrete.]"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_PER_ITEM,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    display_section, what, why, how_to_use, action = _parse_response(text)

    return SummarizedItem(
        title=item.title,
        url=item.url,
        display_section=display_section,
        what=what,
        why=why,
        how_to_use=how_to_use,
        action=action,
        source=ranked.source,
        section=ranked.section,
        original=item,
    )


def _build_source_context(item, section: str) -> str:
    """Extract relevant metadata string from any item type."""
    if section == "github":
        parts = []
        if item.description:
            parts.append(f"Description: {item.description}")
        if item.language:
            parts.append(f"Language: {item.language}")
        parts.append(f"Stars today: {item.stars_today}")
        return "\n".join(parts)
    elif section == "hackernews":
        return f"HN Score: {item.score} | Comments: {item.comments}\nURL: {item.url}"
    elif section == "rss":
        parts = [f"Source: {item.feed_name}", f"Category: {item.category}"]
        if item.summary:
            parts.append(f"Excerpt: {item.summary[:300]}")
        return "\n".join(parts)
    return ""


def _parse_response(text: str) -> tuple[str, str, str, str, str]:
    """Extract SECTION, WHAT, WHY, HOW, ACTION from Claude's structured response."""
    display_section = "signals"
    what = ""
    why = ""
    how_to_use = ""
    action = ""

    for line in text.splitlines():
        if line.startswith("SECTION:"):
            val = line[len("SECTION:"):].strip().lower()
            if val in DISPLAY_SECTIONS:
                display_section = val
        elif line.startswith("WHAT:"):
            what = line[len("WHAT:"):].strip()
        elif line.startswith("WHY:"):
            why = line[len("WHY:"):].strip()
        elif line.startswith("HOW:"):
            how_to_use = line[len("HOW:"):].strip()
        elif line.startswith("ACTION:"):
            action = line[len("ACTION:"):].strip()

    if not what and text:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        what = lines[0] if lines else text[:200]

    return display_section, what, why, how_to_use, action


def _fallback(ranked) -> "SummarizedItem":
    """Return a minimal SummarizedItem when Claude fails."""
    item = ranked.item
    desc = getattr(item, "description", "") or getattr(item, "summary", "") or ""
    return SummarizedItem(
        title=item.title,
        url=item.url,
        display_section="signals",
        what=desc[:200] if desc else item.title,
        why="",
        how_to_use="",
        action="",
        source=ranked.source,
        section=ranked.section,
        original=item,
    )


def _get_client() -> anthropic.Anthropic | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set — summarization disabled")
        return None
    return anthropic.Anthropic(api_key=api_key)
