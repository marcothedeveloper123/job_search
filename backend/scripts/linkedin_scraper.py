#!/usr/bin/env python3
"""
LinkedIn Job Search Scraper

Uses Playwright with persistent browser profile to maintain LinkedIn session.
First run: opens browser for manual login, saves session.
Subsequent runs: reuses saved session automatically.

Usage:
    python linkedin_scraper.py "https://www.linkedin.com/jobs/search/?..."
    python linkedin_scraper.py "https://www.linkedin.com/jobs/search/?..." --dry-run
    python linkedin_scraper.py --login  # Force new login
"""

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# Add backend directory to path for imports when running directly
sys.path.insert(0, str(Path(__file__).parent.parent))
from job_search import ingest_jobs
from scripts.job_filter import filter_jobs

# Persistent profile directory at project root: /data/linkedin_profile/
PROFILE_DIR = Path(__file__).parent.parent.parent / "data" / "linkedin_profile"


# JS: Extract job listings from LinkedIn search results page.
# Finds .job-card-container elements, extracts job ID from /jobs/view/{id}/ links,
# pulls title/company/location from artdeco-entity-lockup elements.
EXTRACTION_JS = """
() => {
    const jobs = [];
    // LinkedIn wraps each job in .job-card-container
    const cards = document.querySelectorAll('.job-card-container');

    cards.forEach(card => {
        // Job link contains the numeric ID in /jobs/view/{id}/
        const link = card.querySelector('a[href*="/jobs/view/"]');
        if (!link) return;

        const href = link.getAttribute('href');
        const jobIdMatch = href.match(/\\/jobs\\/view\\/(\\d+)/);
        if (!jobIdMatch) return;

        // Title is in the link text; strip "with verification" badge suffix
        const title = link.textContent.trim().split('\\n')[0].replace(' with verification', '').trim();
        // Company and location use artdeco lockup pattern
        const companyEl = card.querySelector('.artdeco-entity-lockup__subtitle');
        const company = companyEl ? companyEl.textContent.trim() : '';
        const locationEl = card.querySelector('.artdeco-entity-lockup__caption');
        const location = locationEl ? locationEl.textContent.trim() : '';

        jobs.push({
            id: `job_li_${jobIdMatch[1]}`,
            title,
            company,
            location,
            url: `https://www.linkedin.com/jobs/view/${jobIdMatch[1]}/`,
            source: 'linkedin'
        });
    });

    return jobs;
}
"""

# JS: Scroll the job list to trigger lazy loading.
# Finds scrollable container with job cards and scrolls to bottom.
SCROLL_JS = """
() => {
    const containers = document.querySelectorAll('*');
    for (let el of containers) {
        // Find scrollable element (scrollHeight > visible height) that contains job cards
        if (el.scrollHeight > el.clientHeight && el.clientHeight > 100) {
            if (el.querySelector('.job-card-container')) {
                el.scrollTo(0, el.scrollHeight);
                return true;
            }
        }
    }
    return false;
}
"""

# JS: Extract pagination state ("Page X of Y") to know when to stop.
PAGINATION_INFO_JS = """
() => {
    const pagination = document.querySelector('.jobs-search-pagination');
    if (!pagination) return null;

    // Parse "Page 1 of 5" text
    const pageText = pagination.textContent.match(/Page (\\d+) of (\\d+)/);
    if (!pageText) return null;

    return {
        current: parseInt(pageText[1]),
        total: parseInt(pageText[2])
    };
}
"""


def scroll_and_wait(page, max_scrolls=5, wait_between=1.0):
    """Scroll job list to load all results on current page."""
    for _ in range(max_scrolls):
        scrolled = page.evaluate(SCROLL_JS)
        if not scrolled:
            break
        time.sleep(wait_between)


def extract_jobs(page):
    """Extract job listings from current page."""
    return page.evaluate(EXTRACTION_JS)


def get_pagination(page):
    """Get current pagination state."""
    return page.evaluate(PAGINATION_INFO_JS)


def click_next_page(page):
    """Click next page button. Returns True if successful."""
    try:
        next_btn = page.query_selector('button[aria-label="View next page"]')
        if next_btn and next_btn.is_enabled():
            next_btn.click()
            time.sleep(2)
            return True
    except Exception:
        pass
    return False


def is_logged_in(page) -> bool:
    """Check if user is logged into LinkedIn."""
    # If we see the feed or jobs page elements, we're logged in
    return page.query_selector('input[aria-label*="Search"]') is not None


def do_login(playwright):
    """Open browser for manual login, save session."""
    print("Opening browser for LinkedIn login...", file=sys.stderr)
    print("Please log in. Browser will close automatically when done.", file=sys.stderr)

    # Clear stale lock file from previous runs
    lock_file = PROFILE_DIR / "SingletonLock"
    if lock_file.exists():
        lock_file.unlink()

    context = playwright.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=False,
        channel="chromium",
    )

    page = context.new_page()
    page.goto("https://www.linkedin.com/login")

    # Wait for navigation away from login/checkpoint pages
    print("Waiting for login completion...", file=sys.stderr)
    for _ in range(120):  # 2 minute timeout
        time.sleep(1)
        url = page.url
        if "/feed" in url or "/jobs" in url or "/mynetwork" in url:
            print("Login successful! Session saved.", file=sys.stderr)
            break
    else:
        print("Login timeout. Session may not be saved.", file=sys.stderr)

    context.close()


def scrape_linkedin_search(url: str, max_pages: int = 10, headless: bool = True) -> list[dict]:
    """
    Scrape LinkedIn job search using persistent profile.
    
    Args:
        url: LinkedIn job search URL
        max_pages: Maximum pages to scrape
        headless: Run browser in headless mode
    
    Returns:
        List of job dictionaries
    """
    all_jobs = []
    seen_ids = set()

    # Clear stale lock file from previous runs
    lock_file = PROFILE_DIR / "SingletonLock"
    if lock_file.exists():
        lock_file.unlink()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=headless,
            channel="chromium",
        )
        
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            
            # Check if logged in
            if not is_logged_in(page):
                print("Not logged in. Run with --login first.", file=sys.stderr)
                context.close()
                return []
            
            for page_num in range(max_pages):
                scroll_and_wait(page)
                jobs = extract_jobs(page)
                
                for job in jobs:
                    if job['id'] not in seen_ids:
                        seen_ids.add(job['id'])
                        all_jobs.append(job)
                
                paging = get_pagination(page)
                if paging:
                    print(f"Page {paging['current']} of {paging['total']}: {len(jobs)} jobs", file=sys.stderr)
                    if paging['current'] >= paging['total']:
                        break
                else:
                    print(f"Page {page_num + 1}: {len(jobs)} jobs", file=sys.stderr)
                    break
                
                if not click_next_page(page):
                    break
        
        finally:
            context.close()
    
    return all_jobs


def main():
    parser = argparse.ArgumentParser(description="Scrape LinkedIn job search results")
    parser.add_argument("url", nargs="?", help="LinkedIn job search URL")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON instead of pushing")
    parser.add_argument("--login", action="store_true", help="Open browser for manual login")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    args = parser.parse_args()
    
    PROFILE_DIR.mkdir(exist_ok=True)
    
    if args.login:
        with sync_playwright() as p:
            do_login(p)
        return
    
    if not args.url:
        parser.error("URL required (or use --login)")
    
    print("Scraping LinkedIn...", file=sys.stderr)
    jobs = scrape_linkedin_search(args.url, args.max_pages, headless=not args.visible)
    print(f"Total scraped: {len(jobs)} unique jobs", file=sys.stderr)
    
    # Apply profile-based filtering
    passed, rejected = filter_jobs(jobs)
    print(f"Filtered: {len(passed)} passed, {len(rejected)} rejected", file=sys.stderr)
    
    if rejected:
        print("\nRejected:", file=sys.stderr)
        for job in rejected:
            print(f"  - {job['title']} @ {job['company']}: {job['filter_reason']}", file=sys.stderr)
    
    if args.dry_run:
        print(json.dumps(passed, indent=2))
    else:
        if passed:
            result = ingest_jobs(passed, dedupe_by="job_id")
            print(f"Ingested: added={result.get('added', 0)}, skipped={result.get('skipped', 0)}", file=sys.stderr)
        else:
            print("No jobs passed filtering.", file=sys.stderr)


if __name__ == "__main__":
    main()
