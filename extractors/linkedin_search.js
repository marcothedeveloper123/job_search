/**
 * LinkedIn Job Search Extraction
 *
 * Returns object with extraction functions:
 * - extract(): Main extraction for search results
 * - extractAlt(): Alternate extraction for recommended/collections pages
 * - scroll(): Scroll to trigger lazy loading
 */
(() => {
    return {
        // Main extraction for search results page
        extract: () => {
            const jobs = [];
            const cards = document.querySelectorAll('.job-card-container');

            cards.forEach(card => {
                const link = card.querySelector('a[href*="/jobs/view/"]');
                if (!link) return;

                const href = link.getAttribute('href');
                const jobIdMatch = href.match(/\/jobs\/view\/(\d+)/);
                if (!jobIdMatch) return;

                const title = link.textContent.trim().split('\n')[0].replace(' with verification', '').trim();
                const companyEl = card.querySelector('.artdeco-entity-lockup__subtitle');
                const company = companyEl ? companyEl.textContent.trim() : '';
                const locationEl = card.querySelector('.artdeco-entity-lockup__caption');
                const location = locationEl ? locationEl.textContent.trim() : '';

                // Extract posting date - try multiple selectors
                let postedText = '';
                const timeEl = card.querySelector('time');
                if (timeEl) {
                    postedText = timeEl.textContent.trim();
                } else {
                    const footerItems = card.querySelectorAll('.job-card-container__footer-item, .job-card-container__listed-time');
                    for (const item of footerItems) {
                        const text = item.textContent.trim().toLowerCase();
                        if (text.includes('ago') || text.includes('hour') || text.includes('day') || text.includes('week') || text.includes('month')) {
                            postedText = item.textContent.trim();
                            break;
                        }
                    }
                }

                jobs.push({
                    job_id: jobIdMatch[1],
                    title,
                    company,
                    location,
                    posted_text: postedText,
                    url: `https://www.linkedin.com/jobs/view/${jobIdMatch[1]}/`,
                });
            });

            return jobs;
        },

        // Alternate extraction for recommended/collections pages
        extractAlt: () => {
            const jobs = [];

            const selectors = [
                '.jobs-search-results__list-item',
                '[data-job-id]',
                '.job-card-list__entity-lockup',
                '.jobs-job-board-list__item',
                'li[class*="job"]'
            ];

            let cards = [];
            for (const sel of selectors) {
                cards = document.querySelectorAll(sel);
                if (cards.length > 0) break;
            }

            cards.forEach(card => {
                const link = card.querySelector('a[href*="/jobs/view/"]');
                if (!link) return;

                const href = link.getAttribute('href');
                const jobIdMatch = href.match(/\/jobs\/view\/(\d+)/);
                if (!jobIdMatch) return;

                let title = '';
                const titleEl = card.querySelector('.job-card-list__title, .artdeco-entity-lockup__title, [class*="title"]');
                if (titleEl) {
                    title = titleEl.textContent.trim().split('\n')[0].replace(' with verification', '').trim();
                } else {
                    title = link.textContent.trim().split('\n')[0].replace(' with verification', '').trim();
                }

                let company = '';
                const companyEl = card.querySelector('.job-card-container__primary-description, .artdeco-entity-lockup__subtitle, [class*="company"], [class*="subtitle"]');
                if (companyEl) company = companyEl.textContent.trim();

                let location = '';
                const locationEl = card.querySelector('.job-card-container__metadata-item, .artdeco-entity-lockup__caption, [class*="location"], [class*="caption"]');
                if (locationEl) location = locationEl.textContent.trim();

                jobs.push({
                    job_id: jobIdMatch[1],
                    title,
                    company,
                    location,
                    posted_text: '',
                    url: `https://www.linkedin.com/jobs/view/${jobIdMatch[1]}/`,
                });
            });

            return jobs;
        },

        // Scroll to trigger lazy loading
        scroll: () => {
            const containers = document.querySelectorAll('*');
            for (let el of containers) {
                if (el.scrollHeight > el.clientHeight && el.clientHeight > 100) {
                    if (el.querySelector('.job-card-container') || el.querySelector('[data-job-id]') || el.querySelector('.jobs-search-results__list-item')) {
                        el.scrollTo(0, el.scrollHeight);
                        return true;
                    }
                }
            }
            return false;
        }
    };
})()
