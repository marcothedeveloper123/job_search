/**
 * EU Remote Jobs Extraction
 *
 * Extracts job listings from euremotejobs.com search page.
 * Finds all /job/{slug} links, parses title/company/location from link text,
 * extracts "Posted X days ago" pattern and salary (£/€/$) from text content.
 */
(() => {
    const jobs = [];
    const links = document.querySelectorAll('a[href*="/job/"]');
    const seen = new Set();

    links.forEach(link => {
        const href = link.getAttribute('href');
        if (!href) return;

        // Extract job slug from URL
        const slugMatch = href.match(/\/job\/([^/]+)/);
        if (!slugMatch) return;
        const slug = slugMatch[1];

        // Dedupe by slug
        if (seen.has(slug)) return;
        seen.add(slug);

        // Parse the link text content (title, company, location, tags, posted)
        const text = link.innerText.trim();
        const lines = text.split('\n').map(l => l.trim()).filter(l => l);

        // First line is title
        const title = lines[0] || '';

        // Second line is usually company
        const company = lines[1] || '';

        // Third line is location
        const location = lines[2] || '';

        // Look for posted date pattern in lines
        let postedText = null;
        for (const line of lines) {
            const agoMatch = line.match(/Posted\s+(\d+\s*(?:hour|day|week|month)s?\s*ago)/i);
            if (agoMatch) {
                postedText = agoMatch[1];
                break;
            }
        }

        // Look for salary pattern
        let salary = null;
        const salaryMatch = text.match(/[£€$][\d,]+(?:\s*[-–]\s*[£€$]?[\d,]+)?/);
        if (salaryMatch) salary = salaryMatch[0];

        jobs.push({
            slug: slug,
            title: title,
            company: company,
            location: location,
            salary: salary,
            postedText: postedText,
            url: href.startsWith('http') ? href : 'https://euremotejobs.com' + href
        });
    });

    return jobs;
})()
