"""Shared utilities for JD scrapers - HTML-to-markdown conversion and date parsing."""

import re
from datetime import datetime, timedelta
from typing import Optional

from markdownify import markdownify as md


def fix_html(html: str) -> str:
    """Fix HTML structure before markdown conversion."""
    html = re.sub(r'<span>\s*<br\s*/?>\s*</span>', '<br>', html)
    html = re.sub(r'((?:<br\s*/?>)+)\s*</strong>', r'</strong>\1', html)
    html = re.sub(r'((?:<br\s*/?>)+)\s*</em>', r'</em>\1', html)
    return html


def fix_md(text: str) -> str:
    """Fix markdown spacing issues from HTML conversion."""
    text = re.sub(r'\*\*([^*]+)\*\*', lambda m: '**' + m.group(1).strip() + '**', text)
    text = re.sub(r'\*\*([^*]+)\*\*([a-zA-Z0-9])', r'**\1** \2', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*([a-zA-Z0-9])', r'*\1* \2', text)
    text = re.sub(r'\*\*\*\*', '**\n\n**', text)
    return text


def html_to_md(html: str) -> str:
    """Convert HTML to clean markdown."""
    html = fix_html(html)
    markdown = md(html, heading_style="ATX", bullets="-").strip()
    return fix_md(markdown)


def parse_days_ago_en(text: str) -> Optional[int]:
    """Parse English 'X days/weeks/months ago' to integer days."""
    if not text:
        return None
    text = text.lower().strip()
    if "just" in text or "now" in text or "today" in text or "hour" in text:
        return 0
    if "yesterday" in text:
        return 1
    match = re.search(r"(\d+)\s*(day|week|month)", text)
    if match:
        num, unit = int(match.group(1)), match.group(2)
        return num * (7 if "week" in unit else 30 if "month" in unit else 1)
    return None


def parse_days_ago_cs(text: str) -> Optional[int]:
    """Parse Czech 'před X dny/týdny' to integer days."""
    if not text:
        return None
    text = text.lower().strip()
    if "dnes" in text:
        return 0
    if "včera" in text:
        return 1
    if "před týdnem" in text:
        return 7
    match = re.search(r"před\s+(\d+)\s*(dn|den|dny)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"před\s+(\d+)\s*týdn", text)
    if match:
        return int(match.group(1)) * 7
    return parse_days_ago_en(text)  # Fallback to English


def days_ago_to_iso(days_ago: int) -> str:
    """Convert days ago to ISO date string."""
    return (datetime.utcnow() - timedelta(days=days_ago)).isoformat() + "Z"


def now_iso() -> str:
    """Current UTC time as ISO string."""
    return datetime.utcnow().isoformat() + "Z"


def parse_iso_date(date_str: str) -> Optional[int]:
    """Parse ISO date to days ago."""
    if not date_str:
        return None
    try:
        date_str = date_str.split("T")[0]
        posted = datetime.fromisoformat(date_str)
        return max(0, (datetime.utcnow() - posted).days)
    except (ValueError, TypeError):
        return None
