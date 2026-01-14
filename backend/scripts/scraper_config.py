"""Scraper configuration loader with fallback support.

Config files live in data/scrapers/{name}.json. If missing or invalid,
scrapers use their hardcoded defaults.
"""

import json
from pathlib import Path
from typing import Any, Optional


# Config directory at project root
CONFIG_DIR = Path(__file__).parent.parent.parent / "data" / "scrapers"


def load_config(name: str) -> Optional[dict]:
    """Load scraper config by name. Returns None if missing or invalid.

    Args:
        name: Scraper name (e.g., "linkedin", "jobscz")

    Returns:
        Config dict or None
    """
    config_path = CONFIG_DIR / f"{name}.json"
    if not config_path.exists():
        return None

    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def get_selector(config: Optional[dict], key: str, default: str) -> str:
    """Get selector from config with fallback.

    Args:
        config: Config dict (may be None)
        key: Selector key (e.g., "card", "title")
        default: Fallback value if config missing or key not found

    Returns:
        Selector string
    """
    if config is None:
        return default
    selectors = config.get("selectors", {})
    return selectors.get(key) or default


def get_config_value(config: Optional[dict], path: str, default: Any) -> Any:
    """Get nested config value with fallback.

    Args:
        config: Config dict (may be None)
        path: Dot-separated path (e.g., "pagination.type", "url_pattern.job_id_regex")
        default: Fallback value

    Returns:
        Config value or default
    """
    if config is None:
        return default

    parts = path.split(".")
    value = config
    for part in parts:
        if not isinstance(value, dict):
            return default
        value = value.get(part)
        if value is None:
            return default

    return value


def build_extraction_js(config: Optional[dict], default_js: str) -> str:
    """Get extraction JS from config or use default.

    Args:
        config: Config dict (may be None)
        default_js: Fallback JS code

    Returns:
        JavaScript extraction code
    """
    if config is None:
        return default_js

    # Check for custom extraction JS
    custom_js = config.get("extraction_js")
    if custom_js:
        return custom_js

    # Check if we should build JS from selectors
    selectors = config.get("selectors", {})
    if not selectors.get("card"):
        return default_js

    # Build JS from config selectors - escape single quotes for JS strings
    def esc(s: str) -> str:
        return (s or "").replace("'", "\\'")

    card = esc(selectors.get("card") or ".job-card")
    title = esc(selectors.get("title") or "a")
    company = esc(selectors.get("company") or ".company")
    location = esc(selectors.get("location") or ".location")
    posted = esc(selectors.get("posted") or "time")

    url_pattern = config.get("url_pattern", {})
    job_id_regex = url_pattern.get("job_id_regex", "/jobs/(\\d+)")
    # Escape for JS regex literal: backslashes and forward slashes
    job_id_regex_escaped = job_id_regex.replace("\\", "\\\\").replace("/", "\\/")

    return f"""
() => {{
    const jobs = [];
    const cards = document.querySelectorAll('{card}');

    cards.forEach(card => {{
        const titleEl = card.querySelector('{title}');
        if (!titleEl) return;

        const href = titleEl.getAttribute('href') || '';
        const idMatch = href.match(/{job_id_regex_escaped}/);
        if (!idMatch) return;

        const companyEl = card.querySelector('{company}');
        const locationEl = card.querySelector('{location}');
        const postedEl = card.querySelector('{posted}');

        jobs.push({{
            job_id: idMatch[1],
            title: titleEl.textContent.trim().split('\\n')[0].trim(),
            company: companyEl ? companyEl.textContent.trim() : '',
            location: locationEl ? locationEl.textContent.trim() : '',
            posted_text: postedEl ? postedEl.textContent.trim() : '',
            url: href.startsWith('http') ? href : window.location.origin + href
        }});
    }});

    return jobs;
}}
"""
