"""
Generates a Markdown version of the daily AI intelligence report.
Saved to disk as a local archive alongside the email send.
"""
from __future__ import annotations

from datetime import datetime, timezone


SECTION_HEADERS = {
    "github": "GitHub Trending",
    "hackernews": "Hacker News",
    "rss": "AI News",
}


def build(
    summarized_items: list,
    briefing_intro: str,
    date_str: str,
    sections_order: list[str] | None = None,
) -> str:
    """
    Build a Markdown report string from summarized items.
    Args:
        summarized_items: List of SummarizedItem
        briefing_intro: Intro paragraph from Claude
        date_str: Human-readable date, e.g. "April 16, 2026"
        sections_order: Order to render sections. Defaults to github/hackernews/rss.
    """
    sections_order = sections_order or ["github", "hackernews", "rss"]
    lines = []

    lines.append(f"# Daily AI Intelligence Report — {date_str}\n")

    if briefing_intro:
        lines.append(f"{briefing_intro}\n")

    # Group by section
    by_section: dict[str, list] = {s: [] for s in sections_order}
    for item in summarized_items:
        if item.section in by_section:
            by_section[item.section].append(item)

    for section in sections_order:
        items = by_section.get(section, [])
        if not items:
            continue

        header = SECTION_HEADERS.get(section, section.title())
        lines.append(f"## {header}\n")

        for i, item in enumerate(items, 1):
            lines.append(f"### {i}. [{item.title}]({item.url})\n")
            if item.summary:
                lines.append(f"{item.summary}\n")
            if item.insight:
                lines.append(f"> **Insight:** {item.insight}\n")
            lines.append("")  # blank line between items

    lines.append("---")
    lines.append(f"*Generated {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n")

    return "\n".join(lines)


def save(content: str, output_dir: str = "reports") -> str:
    """
    Save Markdown report to disk. Returns the file path.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    date_slug = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(output_dir, f"ai-report-{date_slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
