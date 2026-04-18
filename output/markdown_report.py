"""
Generates a Markdown version of the daily AI intelligence report.
Saved to disk as a local archive alongside the email send.
"""
from __future__ import annotations

from datetime import datetime, timezone


SECTION_HEADERS = {
    "money_moves":  "Money Moves",
    "platforms":    "Platforms to Watch",
    "systems":      "Systems to Copy",
    "distribution": "Distribution Plays",
    "signals":      "Early Signals",
}

SECTIONS_ORDER = ["money_moves", "platforms", "systems", "distribution", "signals"]


def build(
    summarized_items: list,
    briefing_intro: str,
    date_str: str,
    sections_order: list[str] | None = None,
) -> str:
    sections_order = sections_order or SECTIONS_ORDER
    lines = []

    lines.append(f"# Daily AI Intelligence Report — {date_str}\n")

    if briefing_intro:
        lines.append(f"{briefing_intro}\n")

    by_section: dict[str, list] = {s: [] for s in sections_order}
    for item in summarized_items:
        ds = getattr(item, "display_section", item.section)
        if ds in by_section:
            by_section[ds].append(item)

    for section in sections_order:
        items = by_section.get(section, [])
        if not items:
            continue

        header = SECTION_HEADERS.get(section, section.title())
        lines.append(f"## {header}\n")

        for i, item in enumerate(items, 1):
            lines.append(f"### {i}. [{item.title}]({item.url})\n")
            if getattr(item, "what", ""):
                lines.append(f"{item.what}\n")
            if getattr(item, "why", ""):
                lines.append(f"> **Why it matters:** {item.why}\n")
            if getattr(item, "how_to_use", ""):
                lines.append(f"> **How I could use this:** {item.how_to_use}\n")
            if getattr(item, "action", ""):
                lines.append(f"> **Action:** {item.action}\n")
            lines.append("")

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
