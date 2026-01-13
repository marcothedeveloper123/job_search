#!/usr/bin/env python3
"""
LinkedIn Job Description Scraper

Extracts job descriptions from LinkedIn job postings using Playwright.

Usage:
    python linkedin_jd_scraper.py <job_id_or_url>
    python linkedin_jd_scraper.py 4338710995
    python linkedin_jd_scraper.py https://www.linkedin.com/jobs/view/4338710995/

    # Output as JSON
    python linkedin_jd_scraper.py 4338710995 --json

    # Update deep dive in job_search
    python linkedin_jd_scraper.py 4338710995 --update-deep-dive job_li_4338710995
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

# Add backend directory to path for imports when running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from markdownify import markdownify as md
from playwright.async_api import async_playwright


def _fix_html_before_markdown(html: str) -> str:
    """Fix HTML structure issues before markdown conversion."""
    # Simplify <span><br></span> to just <br>
    html = re.sub(r'<span>\s*<br\s*/?>\s*</span>', '<br>', html)
    # Move <br> tags from inside <strong>/<em> to outside
    # <strong>text<br><br></strong> → <strong>text</strong><br><br>
    html = re.sub(r'((?:<br\s*/?>)+)\s*</strong>', r'</strong>\1', html)
    html = re.sub(r'((?:<br\s*/?>)+)\s*</em>', r'</em>\1', html)
    return html


def _fix_markdown_spacing(text: str) -> str:
    """Fix common markdown spacing issues from HTML-to-markdown conversion."""
    # Trim spaces inside bold markers: ** text** → **text**
    text = re.sub(r'\*\*([^*]+)\*\*', lambda m: '**' + m.group(1).strip() + '**', text)
    # Add space after closing ** when followed by word char (no space in HTML)
    text = re.sub(r'\*\*([^*]+)\*\*([a-zA-Z0-9])', r'**\1** \2', text)
    # Add space after closing * when followed by word char
    text = re.sub(r'(?<!\*)\*([^*]+)\*([a-zA-Z0-9])', r'*\1* \2', text)
    # Fix concatenated bold markers like ****
    text = re.sub(r'\*\*\*\*', '**\n\n**', text)
    return text

# Profile directory at project root (shared with linkedin_scraper.py)
PROFILE_DIR = Path(__file__).parent.parent.parent / "data" / "linkedin_profile"


def extract_job_id(input_str: str) -> str:
    """Extract numeric job ID from URL or raw ID."""
    # Already a numeric ID
    if input_str.isdigit():
        return input_str
    # Extract from URL
    match = re.search(r'/jobs/view/(\d+)', input_str)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract job ID from: {input_str}")


def _parse_days_ago(text: str) -> int | None:
    """Parse 'X days/weeks/months ago' text to integer days."""
    if not text:
        return None
    text = text.lower().strip()

    if "just" in text or "now" in text or "today" in text:
        return 0
    if "yesterday" in text:
        return 1
    if "hour" in text:
        return 0

    match = re.search(r"(\d+)\s*(day|week|month)", text)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        if "week" in unit:
            return num * 7
        if "month" in unit:
            return num * 30
        return num

    return None


async def scrape_job_description(job_id: str, use_profile: bool = True) -> dict:
    """
    Scrape job description from LinkedIn.

    Args:
        job_id: Numeric LinkedIn job ID
        use_profile: Use persistent profile for auth (default True)

    Returns:
        dict with: title, company, location, description, posted_text, days_ago, url, error
    """
    url = f"https://www.linkedin.com/jobs/view/{job_id}/"
    result = {
        "job_id": job_id,
        "url": url,
        "title": None,
        "company": None,
        "location": None,
        "description": None,
        "posted_text": None,
        "days_ago": None,
        "error": None,
    }

    async with async_playwright() as p:
        # Use persistent context if profile exists (for auth)
        if use_profile and PROFILE_DIR.exists():
            # Clear stale lock
            lock_file = PROFILE_DIR / "SingletonLock"
            if lock_file.exists():
                lock_file.unlink()

            context = await p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=True,
                channel="chromium",
            )
            page = await context.new_page()
        else:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)  # Let dynamic content load

            # Check for auth wall
            if "linkedin.com/signup" in page.url or "linkedin.com/login" in page.url:
                result["error"] = "Login required. Run: python linkedin_scraper.py --login"
                return result

            # Title (h1)
            title_el = await page.query_selector("h1")
            if title_el:
                result["title"] = (await title_el.inner_text()).strip()

            # Company (link to company page)
            company_el = await page.query_selector('a[href*="/company/"]')
            if company_el:
                result["company"] = (await company_el.inner_text()).strip()

            # Location (in top card)
            loc_el = await page.query_selector(".job-details-jobs-unified-top-card__primary-description-container span")
            if loc_el:
                result["location"] = (await loc_el.inner_text()).strip()

            # Posting date - look in top card container for "X ago" pattern
            # LinkedIn shows "2 weeks ago · 100 applicants" in the primary description
            top_card = await page.query_selector(".job-details-jobs-unified-top-card__primary-description-container")
            if top_card:
                top_text = await top_card.inner_text()
                # Look for patterns like "2 weeks ago", "3 days ago", "1 month ago"
                time_match = re.search(r"(\d+\s+(?:hour|day|week|month)s?\s+ago)", top_text, re.I)
                if time_match:
                    result["posted_text"] = time_match.group(1)
                    result["days_ago"] = _parse_days_ago(result["posted_text"])

            # Job description - try selectors in order of reliability
            desc_selectors = [
                ".show-more-less-html__markup",  # Best - main description
                ".jobs-description__content",
                ".jobs-box__html-content",
                "article",
            ]

            for selector in desc_selectors:
                desc_el = await page.query_selector(selector)
                if desc_el:
                    # Get HTML and convert to markdown for styling
                    html = await desc_el.inner_html()
                    html = _fix_html_before_markdown(html)
                    markdown = md(html, heading_style="ATX", bullets="-").strip()
                    result["description"] = _fix_markdown_spacing(markdown)
                    break

            if not result["description"]:
                result["error"] = "Could not find job description element"

        except Exception as e:
            result["error"] = str(e)

        finally:
            await context.close()

    return result


async def scrape_multiple(job_ids: list[str]) -> list[dict]:
    """Scrape multiple job descriptions."""
    results = []

    async with async_playwright() as p:
        if PROFILE_DIR.exists():
            lock_file = PROFILE_DIR / "SingletonLock"
            if lock_file.exists():
                lock_file.unlink()
            context = await p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=True,
                channel="chromium",
            )
            page = await context.new_page()
        else:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

        try:
            for job_id in job_ids:
                url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                result = {"job_id": job_id, "url": url}

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)

                    # Title
                    title_el = await page.query_selector("h1")
                    result["title"] = (await title_el.inner_text()).strip() if title_el else None

                    # Description - get HTML and convert to markdown
                    desc_el = await page.query_selector(".show-more-less-html__markup")
                    if desc_el:
                        html = await desc_el.inner_html()
                        html = _fix_html_before_markdown(html)
                        markdown = md(html, heading_style="ATX", bullets="-").strip()
                        result["description"] = _fix_markdown_spacing(markdown)
                    else:
                        result["description"] = None

                    # Rate limit courtesy
                    await page.wait_for_timeout(1000)

                except Exception as e:
                    result["error"] = str(e)

                results.append(result)
                print(f"Scraped {job_id}: {result.get('title', 'ERROR')}", file=sys.stderr)

        finally:
            await context.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="Scrape LinkedIn job descriptions")
    parser.add_argument("job_id", help="Job ID or LinkedIn URL")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--update-deep-dive", metavar="JOB_ID",
                        help="Update deep dive with this job ID")
    args = parser.parse_args()

    try:
        job_id = extract_job_id(args.job_id)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Scraping job {job_id}...", file=sys.stderr)
    result = asyncio.run(scrape_job_description(job_id))

    if result["error"]:
        print(f"Error: {result['error']}", file=sys.stderr)
        if not args.json:
            sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\nTitle: {result['title']}")
        print(f"Company: {result['company']}")
        print(f"Location: {result['location']}")
        print(f"\nDescription:\n{'-' * 40}")
        if result["description"]:
            # Truncate for terminal display
            desc = result["description"]
            if len(desc) > 3000:
                desc = desc[:3000] + "\n... [truncated]"
            print(desc)

    # Update deep dive if requested
    if args.update_deep_dive and result["description"]:
        from job_search import update_deep_dive, update_job
        from datetime import datetime, timedelta

        # Update deep dive with JD
        resp = update_deep_dive(
            args.update_deep_dive,
            jd={
                "raw_text": result["description"],
                "scraped_at": datetime.utcnow().isoformat() + "Z",
                "source_url": result["url"],
                "scrape_status": "complete",
            }
        )
        print(f"\nUpdated deep dive: {resp}", file=sys.stderr)

        # Update job with posting date if available
        if result.get("days_ago") is not None:
            posted = (datetime.utcnow() - timedelta(days=result["days_ago"])).isoformat() + "Z"
            update_job(args.update_deep_dive, {
                "days_ago": result["days_ago"],
                "posted": posted,
            })
            print(f"Updated job posting date: {result['days_ago']} days ago", file=sys.stderr)


if __name__ == "__main__":
    main()
