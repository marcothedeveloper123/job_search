"""Remote extractor fetching with local caching."""

import sys
import time
from pathlib import Path

import requests

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/marcothedeveloper123/job_search/main/extractors"
CACHE_DIR = Path.home() / ".job_search" / "extractors"
CACHE_TTL = 3600  # 1 hour


def get_extractor_js(source: str) -> str:
    """Fetch extractor JS from GitHub with caching.

    Returns the JS code for the given source (e.g., "glassdoor").
    Uses local cache if fresh (<1 hour), otherwise fetches from GitHub.
    Falls back to stale cache if network fails.
    """
    cache_file = CACHE_DIR / f"{source}.js"

    # Check cache
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < CACHE_TTL:
            return cache_file.read_text()

    # Fetch from GitHub
    url = f"{GITHUB_RAW_BASE}/{source}.js"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        js_code = resp.text

        # Cache it
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(js_code)
        return js_code
    except Exception as e:
        # Fall back to cache even if stale
        if cache_file.exists():
            print(f"Network error, using cached {source} extractor", file=sys.stderr)
            return cache_file.read_text()
        raise RuntimeError(f"Cannot fetch {source} extractor: {e}")


def clear_cache(source: str | None = None) -> None:
    """Clear cached extractors.

    If source is None, clears all cached extractors.
    """
    if not CACHE_DIR.exists():
        return

    if source:
        cache_file = CACHE_DIR / f"{source}.js"
        if cache_file.exists():
            cache_file.unlink()
    else:
        for f in CACHE_DIR.glob("*.js"):
            f.unlink()
