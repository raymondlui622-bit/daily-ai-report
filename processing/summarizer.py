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
MAX_TOKENS_PER_ITEM = 300
MAX_TOKENS_BRIEFING = 400


@dataclass
class SummarizedItem:
    title: str
    url: str
    summary: str           # 2-sentence factual summary
    insight: str           # operator insight / "so what"
    source: str
    section: str
    original: object       # reference back to the original dataclass


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

    prompt = f"""You are writing a morning AI intelligence briefing for {date_str}.

Below are today's top AI/tech stories:{context_line}

{titles_str}

Write a 3-4 sentence executive summary that identifies the 2-3 dominant themes across these stories.
Be specific, direct, and insightful — not generic. No bullet points. No greeting. Just the paragraph."""

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

    prompt = f"""You are an AI intelligence analyst writing concise briefings for a technically literate audience tracking the AI/tech industry.{context_line}

Item details:
Title: {item.title}
Source: {ranked.source}
{source_context}

Respond with exactly this format (no extra text):

SUMMARY: [2 sentences. First: what it is. Second: key technical or business detail.]
INSIGHT: [1 sentence. The practical "so what" — why this matters for someone building with AI or investing in the space.]"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_PER_ITEM,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    summary, insight = _parse_response(text)

    return SummarizedItem(
        title=item.title,
        url=item.url,
        summary=summary,
        insight=insight,
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


def _parse_response(text: str) -> tuple[str, str]:
    """Extract SUMMARY and INSIGHT from Claude's structured response."""
    summary = ""
    insight = ""

    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            summary = line[len("SUMMARY:"):].strip()
        elif line.startswith("INSIGHT:"):
            insight = line[len("INSIGHT:"):].strip()

    # Fallback: split on newlines if format not followed
    if not summary and text:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        summary = lines[0] if lines else text[:200]
        insight = lines[1] if len(lines) > 1 else ""

    return summary, insight


def _fallback(ranked) -> "SummarizedItem":
    """Return a minimal SummarizedItem when Claude fails."""
    item = ranked.item
    desc = getattr(item, "description", "") or getattr(item, "summary", "") or ""
    return SummarizedItem(
        title=item.title,
        url=item.url,
        summary=desc[:200] if desc else item.title,
        insight="",
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
