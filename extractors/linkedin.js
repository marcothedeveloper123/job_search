() => {
    const result = {};
    const text = document.body.innerText || '';

    // Company name from h1
    const h1 = document.querySelector('h1');
    if (h1) {
        result.name = h1.innerText.trim();
    }

    // Look for "About" section data - LinkedIn uses dt/dd pairs
    const dts = document.querySelectorAll('dt');
    for (const dt of dts) {
        const label = dt.innerText.trim().toLowerCase();
        const dd = dt.nextElementSibling;
        if (!dd || dd.tagName !== 'DD') continue;
        const value = dd.innerText.trim();

        if (label.includes('website')) {
            const link = dd.querySelector('a');
            if (link) result.website = link.href;
        } else if (label.includes('industry')) {
            result.industry = value;
        } else if (label.includes('company size') || label.includes('employees')) {
            // Extract employee count - look for patterns like "501-1,000" or "1,001-5,000"
            const empMatch = value.match(/([\d,]+(?:-[\d,]+)?)/);
            if (empMatch) result.employees = empMatch[1];
        } else if (label.includes('headquarters')) {
            result.hq = value;
        } else if (label.includes('founded')) {
            const yearMatch = value.match(/(\d{4})/);
            if (yearMatch) result.founded = yearMatch[1];
        } else if (label.includes('type')) {
            result.type = value;
        } else if (label.includes('specialties')) {
            result.specialties = value.split(',').map(s => s.trim()).filter(s => s);
        }
    }

    // Fallback: extract from page text if dt/dd didn't work
    if (!result.employees) {
        // Look for "X employees on LinkedIn" or "X,XXX employees"
        const empMatch = text.match(/([\d,]+(?:-[\d,]+)?)\s+employees\s+on\s+LinkedIn/i) ||
                        text.match(/Company size\s*([\d,]+(?:-[\d,]+)?)/i);
        if (empMatch) result.employees = empMatch[1];
    }

    if (!result.hq) {
        const hqMatch = text.match(/Headquarters?\s*([^\n]{5,50})/i);
        if (hqMatch) result.hq = hqMatch[1].trim();
    }

    if (!result.industry) {
        const indMatch = text.match(/Industry\s*([^\n]{5,50})/i);
        if (indMatch) result.industry = indMatch[1].trim();
    }

    if (!result.founded) {
        const foundedMatch = text.match(/Founded\s*(\d{4})/i);
        if (foundedMatch) result.founded = foundedMatch[1];
    }

    // Description - look for "Overview" or "About" section
    const descEl = document.querySelector('[class*="description"]') ||
                   document.querySelector('[class*="about-us"]');
    if (descEl) {
        const desc = descEl.innerText.trim();
        if (desc.length > 50) {
            result.description = desc.length > 500 ? desc.slice(0, 500) + '...' : desc;
        }
    }

    return result;
}
