() => {
    const result = {};
    const text = document.body.innerText || '';

    // Try JSON-LD structured data first (G2 uses schema.org)
    const jsonLd = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of jsonLd) {
        try {
            const data = JSON.parse(script.textContent);
            // Handle both single object and array
            const items = Array.isArray(data) ? data : [data];
            for (const item of items) {
                if (item['@type'] === 'Product' || item['@type'] === 'SoftwareApplication') {
                    if (item.name) result.product = item.name;
                    if (item.aggregateRating) {
                        result.rating = parseFloat(item.aggregateRating.ratingValue);
                        result.reviews = parseInt(item.aggregateRating.reviewCount);
                    }
                }
                if (item['@type'] === 'AggregateRating') {
                    result.rating = parseFloat(item.ratingValue);
                    result.reviews = parseInt(item.reviewCount);
                }
            }
        } catch (e) {}
    }

    // Extract product name if not found
    if (!result.product) {
        const h1 = document.querySelector('h1');
        if (h1) {
            const name = h1.innerText.trim();
            if (name.length < 100) {
                result.product = name.replace(/\s*Reviews?\s*$/i, '').trim();
            }
        }
    }

    // Extract rating from visible text if not found
    if (!result.rating) {
        const ratingMatch = text.match(/(\d\.\d)\s*(?:out of 5|stars|rating|overall)/i) ||
                           text.match(/(?:Rating|Score)[:\s]*(\d\.\d)/i);
        if (ratingMatch) {
            result.rating = parseFloat(ratingMatch[1]);
        }
    }

    // Extract review count
    if (!result.reviews) {
        const reviewMatch = text.match(/([\d,]+)\s*(?:Reviews?|reviews?|ratings?)/);
        if (reviewMatch) {
            result.reviews = parseInt(reviewMatch[1].replace(/,/g, ''));
        }
    }

    // Category ranking
    const rankMatch = text.match(/#(\d+)\s+(?:in|of)\s+([^\n]{5,50})/i);
    if (rankMatch) {
        result.ranking = {
            position: parseInt(rankMatch[1]),
            category: rankMatch[2].trim()
        };
    }

    // Satisfaction scores
    const satisfaction = {};
    const satisfactionPatterns = {
        'ease_of_use': /Ease\s+of\s+Use[:\s]*(\d+\.?\d?)(?:%|\/10)?/i,
        'ease_of_setup': /Ease\s+of\s+Setup[:\s]*(\d+\.?\d?)(?:%|\/10)?/i,
        'quality_of_support': /(?:Quality\s+of\s+)?Support[:\s]*(\d+\.?\d?)(?:%|\/10)?/i,
        'meets_requirements': /Meets\s+Requirements[:\s]*(\d+\.?\d?)(?:%|\/10)?/i,
    };
    for (const [key, pattern] of Object.entries(satisfactionPatterns)) {
        const match = text.match(pattern);
        if (match) {
            const val = parseFloat(match[1]);
            satisfaction[key] = val <= 10 ? val + '/10' : val + '%';
        }
    }
    if (Object.keys(satisfaction).length > 0) {
        result.satisfaction = satisfaction;
    }

    // Extract pros (what users like)
    const pros = [];
    const prosMatches = text.match(/(?:What\s+(?:do\s+you|users?)\s+like|Pros|Likes?)[:\n]+([^\n]{20,300})/gi) || [];
    for (const match of prosMatches.slice(0, 5)) {
        const content = match.replace(/^(?:What\s+(?:do\s+you|users?)\s+like|Pros|Likes?)[:\n]+/i, '').trim();
        if (content.length > 15 && !content.toLowerCase().includes('what do you')) {
            pros.push(content.length > 200 ? content.slice(0, 200) + '...' : content);
        }
    }
    if (pros.length > 0) result.pros = pros;

    // Extract cons (what users dislike)
    const cons = [];
    const consMatches = text.match(/(?:What\s+(?:do\s+you|users?)\s+dislike|Cons|Dislikes?)[:\n]+([^\n]{20,300})/gi) || [];
    for (const match of consMatches.slice(0, 5)) {
        const content = match.replace(/^(?:What\s+(?:do\s+you|users?)\s+dislike|Cons|Dislikes?)[:\n]+/i, '').trim();
        if (content.length > 15 && !content.toLowerCase().includes('what do you')) {
            cons.push(content.length > 200 ? content.slice(0, 200) + '...' : content);
        }
    }
    if (cons.length > 0) result.cons = cons;

    // Alternatives/competitors
    const altMatch = text.match(/(?:Alternatives?|Competitors?|Compare|vs)[:\n\s]+([^\n]{10,200})/i);
    if (altMatch) {
        const alternatives = altMatch[1]
            .split(/[,\n]/)
            .map(s => s.trim())
            .filter(s => s.length > 2 && s.length < 50)
            .slice(0, 5);
        if (alternatives.length > 0) {
            result.alternatives = alternatives;
        }
    }

    return result;
}
