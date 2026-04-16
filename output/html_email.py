"""
Renders the daily AI intelligence report as an HTML email and sends via Gmail SMTP.
Uses inline CSS for maximum email client compatibility.
"""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SECTION_HEADERS = {
    "github": "GitHub Trending",
    "hackernews": "Hacker News",
    "rss": "AI News & Research",
}

# Inline CSS palette
COLORS = {
    "bg": "#f5f5f5",
    "card_bg": "#ffffff",
    "header_bg": "#1a1a2e",
    "header_text": "#ffffff",
    "accent": "#e94560",
    "section_bg": "#16213e",
    "section_text": "#ffffff",
    "insight_bg": "#fff8e1",
    "insight_border": "#ffc107",
    "link": "#1565c0",
    "muted": "#757575",
    "body_text": "#212121",
    "divider": "#e0e0e0",
}


def build_html(
    summarized_items: list,
    briefing_intro: str,
    date_str: str,
    sections_order: list[str] | None = None,
) -> str:
    """Build full HTML email string."""
    sections_order = sections_order or ["github", "hackernews", "rss"]

    by_section: dict[str, list] = {s: [] for s in sections_order}
    for item in summarized_items:
        if item.section in by_section:
            by_section[item.section].append(item)

    sections_html = ""
    for section in sections_order:
        items = by_section.get(section, [])
        if items:
            sections_html += _render_section(section, items)

    intro_html = f'<p style="font-size:16px;line-height:1.6;color:{COLORS["body_text"]};margin:0 0 24px 0;">{briefing_intro}</p>' if briefing_intro else ""

    generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily AI Intelligence Report — {date_str}</title>
</head>
<body style="margin:0;padding:0;background-color:{COLORS['bg']};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{COLORS['bg']};">
<tr><td align="center" style="padding:24px 16px;">

  <!-- Container -->
  <table width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;">

    <!-- Header -->
    <tr><td style="background-color:{COLORS['header_bg']};border-radius:8px 8px 0 0;padding:32px 32px 24px 32px;">
      <p style="margin:0 0 4px 0;font-size:12px;color:{COLORS['accent']};text-transform:uppercase;letter-spacing:2px;font-weight:600;">Daily Intelligence</p>
      <h1 style="margin:0;font-size:24px;font-weight:700;color:{COLORS['header_text']};line-height:1.2;">AI Intelligence Report</h1>
      <p style="margin:8px 0 0 0;font-size:14px;color:#9e9e9e;">{date_str}</p>
    </td></tr>

    <!-- Intro -->
    <tr><td style="background-color:{COLORS['card_bg']};padding:28px 32px;">
      {intro_html}
    </td></tr>

    <!-- Sections -->
    {sections_html}

    <!-- Footer -->
    <tr><td style="background-color:{COLORS['card_bg']};border-radius:0 0 8px 8px;border-top:1px solid {COLORS['divider']};padding:20px 32px;text-align:center;">
      <p style="margin:0;font-size:12px;color:{COLORS['muted']};">Generated {generated}</p>
    </td></tr>

  </table>
</td></tr>
</table>

</body>
</html>"""


def _render_section(section: str, items: list) -> str:
    header = SECTION_HEADERS.get(section, section.title())
    items_html = "".join(_render_item(item, i + 1) for i, item in enumerate(items))

    return f"""
    <tr><td style="background-color:{COLORS['section_bg']};padding:12px 32px;">
      <h2 style="margin:0;font-size:13px;font-weight:600;color:{COLORS['section_text']};text-transform:uppercase;letter-spacing:1.5px;">{header}</h2>
    </td></tr>
    <tr><td style="background-color:{COLORS['card_bg']};padding:8px 0;">
      {items_html}
    </td></tr>"""


def _render_item(item, index: int) -> str:
    summary_html = f'<p style="margin:6px 0 0 0;font-size:14px;line-height:1.5;color:#424242;">{item.summary}</p>' if item.summary else ""

    insight_html = ""
    if item.insight:
        insight_html = f"""
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:10px;">
      <tr><td style="background-color:{COLORS['insight_bg']};border-left:3px solid {COLORS['insight_border']};padding:10px 14px;border-radius:0 4px 4px 0;">
        <p style="margin:0;font-size:13px;line-height:1.5;color:#5f4339;"><strong>Insight:</strong> {item.insight}</p>
      </td></tr>
      </table>"""

    meta = _render_meta(item)

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td style="padding:16px 32px;border-bottom:1px solid {COLORS['divider']};">
      <p style="margin:0 0 4px 0;font-size:12px;color:{COLORS['muted']};">{index}. {meta}</p>
      <a href="{item.url}" style="font-size:15px;font-weight:600;color:{COLORS['link']};text-decoration:none;line-height:1.3;">{item.title}</a>
      {summary_html}
      {insight_html}
    </td></tr>
    </table>"""


def _render_meta(item) -> str:
    """Render small metadata line under item number."""
    orig = item.original
    if item.section == "github":
        lang = f" · {orig.language}" if getattr(orig, "language", None) else ""
        stars = getattr(orig, "stars_today", 0)
        return f"GitHub{lang} · ⭐ {stars:,} today"
    elif item.section == "hackernews":
        score = getattr(orig, "score", 0)
        comments = getattr(orig, "comments", 0)
        return f"Hacker News · {score} pts · {comments} comments"
    elif item.section == "rss":
        feed = getattr(orig, "feed_name", "")
        published = getattr(orig, "published", None)
        date_part = published.strftime("%b %d") if published else ""
        return f"{feed} · {date_part}" if date_part else feed
    return item.source


def send_email(
    html_content: str,
    subject: str,
    to_addresses: list[str],
) -> bool:
    """
    Send HTML email via Gmail SMTP.
    Reads credentials from env: GMAIL_USER, GMAIL_APP_PASSWORD.
    Returns True on success, False on failure.
    """
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        logger.error("GMAIL_USER or GMAIL_APP_PASSWORD not set")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(to_addresses)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_addresses, msg.as_string())
        logger.info(f"Email sent to {to_addresses}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
