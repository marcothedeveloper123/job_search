() => {
    const result = {};
    const text = document.body.innerText || '';

    // Try JSON-LD structured data first
    const jsonLd = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of jsonLd) {
        try {
            const data = JSON.parse(script.textContent);
            if (data['@type'] === 'Organization' || data['@type'] === 'EmployerAggregateRating') {
                if (data.aggregateRating) {
                    result.rating = parseFloat(data.aggregateRating.ratingValue);
                    result.reviews = parseInt(data.aggregateRating.reviewCount);
                }
                if (data.ratingValue) result.rating = parseFloat(data.ratingValue);
                if (data.reviewCount) result.reviews = parseInt(data.reviewCount);
            }
        } catch (e) {}
    }

    // Rating: look for "X.X ★" pattern or "X.X out of 5"
    if (!result.rating) {
        const ratingMatch = text.match(/(\d\.\d)\s*★/) ||
                           text.match(/(\d\.\d)\s*out of 5/i) ||
                           text.match(/rate[sd]?.*?(\d\.\d)\s*out of 5/i);
        if (ratingMatch) {
            result.rating = parseFloat(ratingMatch[1]);
        }
    }

    // Review count: "based on X reviews" or "X reviews"
    if (!result.reviews) {
        const reviewMatch = text.match(/based on (\d+).*?reviews/i) ||
                           text.match(/(\d+)\s+anonymous reviews/i) ||
                           text.match(/(\d+)\s+reviews/i);
        if (reviewMatch) {
            result.reviews = parseInt(reviewMatch[1]);
        }
    }

    // Recommend percentage: "X% would recommend"
    const recommendMatch = text.match(/(\d+)%\s*would recommend/i);
    if (recommendMatch) {
        result.recommend_pct = recommendMatch[1] + '%';
    }

    // Business outlook: "X% positive business outlook"
    const outlookMatch = text.match(/(\d+)%.*?positive business outlook/i);
    if (outlookMatch) {
        result.business_outlook = outlookMatch[1] + '%';
    }

    // CEO approval
    const ceoMatch = text.match(/(\d+)%\s*(?:approve|approval).*?CEO/i) ||
                    text.match(/CEO.*?(\d+)%/i);
    if (ceoMatch) {
        result.ceo_approval = ceoMatch[1] + '%';
    }

    // Interview info from FAQs section
    const difficultyMatch = text.match(/difficulty.*?(\d\.\d)\s*out of 5/i) ||
                           text.match(/(\d\.\d)\s*out of 5.*?difficulty/i);
    const positiveInterviewMatch = text.match(/(\d+)%.*?rate their.*?interview.*?positive/i) ||
                                   text.match(/(\d+)%.*?positive.*?interview/i);

    if (difficultyMatch || positiveInterviewMatch) {
        result.interview = {};
        if (difficultyMatch) {
            result.interview.difficulty = parseFloat(difficultyMatch[1]);
        }
        if (positiveInterviewMatch) {
            result.interview.positive_pct = positiveInterviewMatch[1] + '%';
        }
    }

    // Ratings breakdown - look for category ratings
    const categories = {
        'Culture': 'culture',
        'Work/Life Balance': 'work_life_balance',
        'Diversity': 'diversity',
        'Compensation': 'compensation',
        'Career Opportunities': 'career_opportunities',
        'Senior Management': 'senior_management'
    };

    const breakdown = {};
    for (const [label, key] of Object.entries(categories)) {
        const pattern = new RegExp(label + '[:\\s]*(\d\\.\\d)', 'i');
        const match = text.match(pattern);
        if (match) {
            breakdown[key] = parseFloat(match[1]);
        }
    }
    if (Object.keys(breakdown).length > 0) {
        result.ratings_breakdown = breakdown;
    }

    // Extract pros and cons from reviews page (if present)
    const pros = [];
    const cons = [];

    const prosMatches = text.match(/Pros[:\n]+([^\n]{20,300})/g) || [];
    const consMatches = text.match(/Cons[:\n]+([^\n]{20,300})/g) || [];

    for (const match of prosMatches.slice(0, 5)) {
        const content = match.replace(/^Pros[:\n]+/, '').trim();
        if (content.length > 15) {
            pros.push(content.length > 200 ? content.slice(0, 200) + '...' : content);
        }
    }

    for (const match of consMatches.slice(0, 5)) {
        const content = match.replace(/^Cons[:\n]+/, '').trim();
        if (content.length > 15) {
            cons.push(content.length > 200 ? content.slice(0, 200) + '...' : content);
        }
    }

    if (pros.length > 0) result.pros = pros;
    if (cons.length > 0) result.cons = cons;

    return result;
}
