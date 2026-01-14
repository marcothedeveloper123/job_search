"""Generic config-driven job description scraper.

Uses scraper config files to extract JD from detail pages.

Config fields used:
- url_pattern.job_url_template: URL pattern with {id} placeholder
- jd.selectors: CSS selectors for description (array, tries in order)
- jd.use_jsonld: Try JSON-LD extraction first (default: true)
- jd.wait_ms: Wait time after page load (default: 2000)

Usage:
    from scripts.generic_jd import scrape_jd_generic, scrape_jds_generic
    result = scrape_jd_generic("indeed_nl", "abc123")
"""

import html as html_lib
import json
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from markdownify import markdownify as md

from scripts.scraper_config import load_config, get_config_value
from scripts.scrape_utils import fix_html, fix_md, now_iso


# JSON-LD extraction JS
EXTRACT_JSONLD_JS = """
() => {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of scripts) {
        try {
            const data = JSON.parse(script.textContent);
            if (data['@type'] === 'JobPosting') return data;
            if (Array.isArray(data)) {
                const job = data.find(d => d['@type'] === 'JobPosting');
                if (job) return job;
            }
        } catch (e) {}
    }
    return null;
}
"""


def _html_to_md(html: str) -> str:
    """Convert HTML to markdown."""
    html = html_lib.unescape(html)
    html = fix_html(html)
    markdown = md(html, heading_style="ATX", bullets="-").strip()
    return fix_md(markdown)


def _build_jd_url(config: dict, job_id: str) -> Optional[str]:
    """Build JD page URL from config template."""
    template = get_config_value(config, "url_pattern.job_url_template", None)
    if not template:
        return None
    return template.replace("{id}", job_id)


def _extract_raw_id(job_id: str, prefix: str) -> str:
    """Extract raw ID from prefixed job_id."""
    full_prefix = f"job_{prefix}_"
    if job_id.startswith(full_prefix):
        return job_id[len(full_prefix):]
    if job_id.startswith(f"{prefix}_"):
        return job_id[len(prefix) + 1:]
    return job_id


def scrape_jd_generic(scraper_name: str, job_id: str, collect_diagnostics: bool = False) -> dict:
    """Scrape job description using config-driven approach."""
    config = load_config(scraper_name)
    if not config:
        return {"status": "error", "error": f"No config for {scraper_name}", "code": "CONFIG_NOT_FOUND"}

    prefix = config.get("id_prefix", scraper_name[:2])
    raw_id = _extract_raw_id(job_id, prefix.rstrip("_"))
    normalized_id = f"job_{prefix}{raw_id}" if not prefix.endswith("_") else f"job_{prefix[:-1]}_{raw_id}"

    url = _build_jd_url(config, raw_id)
    if not url:
        return {"status": "error", "error": "No job_url_template in config", "code": "CONFIG_MISSING"}

    jd_config = config.get("jd", {})
    selectors = jd_config.get("selectors", ["#jobDescriptionText", ".job-description", "article"])
    use_jsonld = jd_config.get("use_jsonld", True)
    wait_ms = jd_config.get("wait_ms", 2000)

    diagnostics = {"url": url, "selectors_tried": []} if collect_diagnostics else None

    try:
        stealth = Stealth()
        with stealth.use_sync(sync_playwright()) as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(wait_ms)

                if collect_diagnostics:
                    diagnostics["page_title"] = page.title()

                jd_text = None

                # Try JSON-LD first
                if use_jsonld:
                    jsonld = page.evaluate(EXTRACT_JSONLD_JS)
                    if jsonld and jsonld.get("description"):
                        jd_text = _html_to_md(jsonld["description"])
                        if collect_diagnostics:
                            diagnostics["source"] = "jsonld"

                # Try selectors
                if not jd_text or len(jd_text) < 100:
                    for selector in selectors:
                        if collect_diagnostics:
                            diagnostics["selectors_tried"].append(selector)
                        el = page.query_selector(selector)
                        if el:
                            jd = _html_to_md(el.inner_html())
                            if len(jd) > 100:
                                jd_text = jd
                                if collect_diagnostics:
                                    diagnostics["source"] = f"selector:{selector}"
                                break

                if not jd_text or len(jd_text) < 100:
                    title = page.title().lower()
                    if "block" in title or "captcha" in title:
                        error = "Bot blocked"
                        code = "BOT_BLOCKED"
                    else:
                        error = "Could not find job description"
                        code = "JD_NOT_FOUND"
                    result = {"status": "error", "error": error, "code": code}
                    if collect_diagnostics:
                        result["diagnostics"] = diagnostics
                    return result

                result = {
                    "status": "ok",
                    "job_id": normalized_id,
                    "jd_text": jd_text,
                    "url": page.url,
                    "scraped_at": now_iso(),
                }
                if collect_diagnostics:
                    result["diagnostics"] = diagnostics
                return result
            finally:
                browser.close()
    except Exception as e:
        result = {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}
        if collect_diagnostics:
            result["diagnostics"] = diagnostics
        return result


def scrape_jds_generic(scraper_name: str, job_ids: list[str]) -> dict:
    """Batch scrape job descriptions using config-driven approach."""
    if not job_ids:
        return {"status": "ok", "results": [], "succeeded": 0, "failed": 0}

    config = load_config(scraper_name)
    if not config:
        return {"status": "error", "error": f"No config for {scraper_name}", "code": "CONFIG_NOT_FOUND"}

    prefix = config.get("id_prefix", scraper_name[:2])
    jd_config = config.get("jd", {})
    selectors = jd_config.get("selectors", ["#jobDescriptionText", ".job-description", "article"])
    use_jsonld = jd_config.get("use_jsonld", True)
    wait_ms = jd_config.get("wait_ms", 2000)

    results, succeeded, failed = [], 0, 0

    try:
        stealth = Stealth()
        with stealth.use_sync(sync_playwright()) as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                for job_id in job_ids:
                    raw_id = _extract_raw_id(job_id, prefix.rstrip("_"))
                    normalized_id = f"job_{prefix}{raw_id}" if not prefix.endswith("_") else f"job_{prefix[:-1]}_{raw_id}"

                    url = _build_jd_url(config, raw_id)
                    if not url:
                        results.append({"job_id": normalized_id, "status": "error", "error": "No URL template"})
                        failed += 1
                        continue

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(wait_ms)

                        jd_text = None

                        if use_jsonld:
                            jsonld = page.evaluate(EXTRACT_JSONLD_JS)
                            if jsonld and jsonld.get("description"):
                                jd_text = _html_to_md(jsonld["description"])

                        if not jd_text or len(jd_text) < 100:
                            for selector in selectors:
                                el = page.query_selector(selector)
                                if el:
                                    jd = _html_to_md(el.inner_html())
                                    if len(jd) > 100:
                                        jd_text = jd
                                        break

                        if jd_text and len(jd_text) > 100:
                            results.append({
                                "job_id": normalized_id,
                                "jd_text": jd_text,
                                "url": page.url,
                                "scraped_at": now_iso(),
                            })
                            succeeded += 1
                        else:
                            title = page.title().lower()
                            error = "Bot blocked" if "block" in title else "JD not found"
                            results.append({"job_id": normalized_id, "status": "error", "error": error})
                            failed += 1

                        page.wait_for_timeout(1500)  # Rate limiting
                    except Exception as e:
                        results.append({"job_id": normalized_id, "status": "error", "error": str(e)})
                        failed += 1
            finally:
                browser.close()
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    return {"status": "ok", "results": results, "succeeded": succeeded, "failed": failed}
