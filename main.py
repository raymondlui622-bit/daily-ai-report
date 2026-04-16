"""
Daily AI Intelligence Report — Orchestrator

Fetches data from GitHub Trending, Hacker News, and RSS feeds independently.
Each source fails gracefully — the report runs with whatever data is available.
Summarizes with Claude, renders HTML email + Markdown report, sends via Gmail.

Usage:
    python main.py                    # run with all defaults
    python main.py --no-email         # generate report only, skip send
    python main.py --dry-run          # fetch + summarize, print to stdout only
    python main.py --output-dir DIR   # save Markdown reports to DIR
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

# Data sources
from data_sources import github_trending, hackernews, rss_feeds

# Processing
from processing import deduplication, ranking, summarizer

# Output
from output import html_email, markdown_report

load_dotenv(override=True)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# ── Config ────────────────────────────────────────────────────────────────────
OPERATOR_CONTEXT = os.getenv(
    "OPERATOR_CONTEXT",
    "The reader is a technically literate entrepreneur and AI practitioner who "
    "wants to stay current on AI tools, models, infrastructure, and business trends. "
    "Prioritize practical implications and signal over hype.",
)

EMAIL_RECIPIENTS = [
    addr.strip()
    for addr in os.getenv("EMAIL_RECIPIENTS", "").split(",")
    if addr.strip()
]

GITHUB_LANGUAGE_FILTER = os.getenv("GITHUB_LANGUAGE_FILTER", "")  # e.g. "python"
HN_AI_ONLY = os.getenv("HN_AI_ONLY", "true").lower() == "true"

SECTIONS_ORDER = ["github", "hackernews", "rss"]
GITHUB_TOP = int(os.getenv("GITHUB_TOP", "5"))
HN_TOP = int(os.getenv("HN_TOP", "7"))
RSS_TOP = int(os.getenv("RSS_TOP", "8"))


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(send_email: bool = True, dry_run: bool = False, output_dir: str = "reports"):
    date_str = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    subject = f"AI Intelligence Report — {datetime.now(tz=timezone.utc).strftime('%b %d, %Y')}"

    logger.info(f"=== Daily AI Intelligence Report — {date_str} ===")

    # 1. Fetch all sources in parallel, each independently fault-tolerant
    github_items, hn_items, rss_items = _fetch_all()

    if not github_items and not hn_items and not rss_items:
        logger.error("All data sources failed. Aborting.")
        sys.exit(1)

    logger.info(
        f"Raw counts — GitHub: {len(github_items)}, HN: {len(hn_items)}, RSS: {len(rss_items)}"
    )

    # 2. Deduplicate within each source (RSS is most likely to have dups)
    rss_items = deduplication.deduplicate(rss_items)

    # 3. Rank by section, cap each
    ranked_by_section = ranking.rank_by_section(
        github_items, hn_items, rss_items,
        github_top=GITHUB_TOP,
        hn_top=HN_TOP,
        rss_top=RSS_TOP,
    )

    # Flatten in section order for summarization
    all_ranked = []
    for section in SECTIONS_ORDER:
        all_ranked.extend(ranked_by_section.get(section, []))

    logger.info(f"Ranked total: {len(all_ranked)} items")

    # 4. Summarize with Claude
    logger.info("Summarizing with Claude...")
    summarized = summarizer.summarize_items(all_ranked, operator_context=OPERATOR_CONTEXT)
    briefing_intro = summarizer.generate_briefing_intro(
        summarized, date_str, operator_context=OPERATOR_CONTEXT
    )

    # 5. Build outputs
    md_content = markdown_report.build(
        summarized, briefing_intro, date_str, SECTIONS_ORDER
    )
    html_content = html_email.build_html(
        summarized, briefing_intro, date_str, SECTIONS_ORDER
    )

    if dry_run:
        print(md_content)
        return

    # 6. Save Markdown archive
    md_path = markdown_report.save(md_content, output_dir=output_dir)
    logger.info(f"Markdown saved: {md_path}")

    # 7. Send email
    if send_email:
        if not EMAIL_RECIPIENTS:
            logger.warning("No EMAIL_RECIPIENTS configured — skipping send")
        else:
            success = html_email.send_email(html_content, subject, EMAIL_RECIPIENTS)
            if success:
                logger.info(f"Email delivered to: {EMAIL_RECIPIENTS}")
            else:
                logger.error("Email delivery failed")
    else:
        logger.info("Email send skipped (--no-email)")

    logger.info("Done.")


def _fetch_all() -> tuple[list, list, list]:
    """Fetch all three sources in parallel. Each returns empty list on failure."""
    results = {"github": [], "hn": [], "rss": []}

    def fetch_github():
        logger.info("Fetching GitHub trending...")
        return "github", github_trending.fetch(language=GITHUB_LANGUAGE_FILTER)

    def fetch_hn():
        logger.info("Fetching Hacker News...")
        return "hn", hackernews.fetch(ai_only=HN_AI_ONLY)

    def fetch_rss():
        logger.info("Fetching RSS feeds...")
        return "rss", rss_feeds.fetch()

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(fetch_github),
            executor.submit(fetch_hn),
            executor.submit(fetch_rss),
        ]
        for future in as_completed(futures):
            try:
                key, data = future.result()
                results[key] = data
            except Exception as e:
                logger.error(f"Source fetch exception: {e}")

    return results["github"], results["hn"], results["rss"]


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Daily AI Intelligence Report")
    parser.add_argument(
        "--no-email", action="store_true",
        help="Generate report but skip email send"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print Markdown to stdout, no files or email"
    )
    parser.add_argument(
        "--output-dir", default="reports",
        help="Directory to save Markdown reports (default: reports/)"
    )
    args = parser.parse_args()

    run(
        send_email=not args.no_email,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
