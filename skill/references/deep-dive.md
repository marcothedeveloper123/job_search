# Deep Dive Standards

Read `data/profile/anti-positioning.md` before qualifying.

## Qualification Gate

**Skip if ANY hard filter fails:**

| Filter | Pass |
|--------|------|
| Title | Contains "Product Manager" (not Design, GTM, Enablement, Coordinator) |
| Level | Senior, Staff, Principal (not Associate, not Director/VP/Head) |
| Location | EU remote, CZ, NL, DE, ES, FR, IT (NOT UK, NOT US-only) |
| AI signal | AI/ML/LLM/GenAI in title or JD |

**Skip if 2+ red flags:**
- "Stakeholder alignment" as primary responsibility
- "Matrix organization" / "dotted-line reporting"
- "Influence without authority"
- "Governance" in any context
- "Advisory" / "strategic liaison"
- "/" in title indicating split role (PM/BA, PM/Tech Lead)

**Need 2+ positive signals to proceed:**
- "Zero-to-one" / "0-1"
- "Ship" / "launch" / "deliver"
- "Hands-on" / "IC"
- "AI agents" / "agentic" / "LLM"
- "Ownership" / "own the product"

**Typical outcome:** 2-4 jobs per search warrant deep dive, not 10+.

## Research Questions

Answer each with sourced claims using markdown links.

### Company

1. **How does the company generate revenue?**
   - Business model (SaaS, marketplace, services, hardware)
   - Pricing (public pricing page, analyst reports)
   - Customer segments (SMB, mid-market, enterprise)

2. **What are the company's finances?**
   - Funding raised, investors, valuation ([Crunchbase](https://crunchbase.com))
   - Revenue if disclosed (annual reports, news, [Growjo](https://growjo.com))
   - Profitability signals (layoffs, hiring freeze, growth rate)

3. **What products does the company make?**
   - Product portfolio from company website
   - Which products drive revenue
   - Product strategy (platform, point solution, suite)

### Product (mentioned in JD)

4. **What do we know about this specific product?**
   - Features, positioning, target user
   - Launch date, maturity, market fit signals
   - Roadmap hints (blog, changelog, job posts)

5. **What do customers say about the product?**
   - [G2](https://g2.com), [TrustRadius](https://trustradius.com), [Capterra](https://capterra.com)
   - Strengths and weaknesses from reviews
   - Competitive alternatives mentioned

### People

6. **What do customers say about the company?**
   - Customer reviews, case studies
   - NPS if disclosed
   - Churn signals (negative reviews, competitor mentions)

7. **What do employees say?**
   - [Glassdoor](https://glassdoor.com), [Blind](https://teamblind.com)
   - About the company culture
   - About the CEO and leadership
   - About salaries and compensation
   - PM-specific reviews if available

### Job Post Analysis

8. **What can we infer from the job post?**
   - Language patterns: count "ship" vs "governance" vs "stakeholder"
   - Scope clarity: is ownership defined or vague?
   - Team structure: who you report to, team size
   - Red flags: matrix, dotted-line, influence without authority
   - Why is this role open? (growth, backfill, reorg)

### Context

9. **Competitive landscape**
   - Who are the main competitors?
   - How does the product differentiate?
   - Market position (leader, challenger, niche)

10. **Recent news**
    - Acquisitions, mergers, or being acquired
    - Layoffs, hiring freezes, or rapid growth
    - Leadership changes (CEO, CPO, key departures)
    - Product pivots or strategic shifts

11. **Tech stack and engineering culture**
    - What technologies does the product use?
    - Engineering blog, open source contributions
    - How do PMs and engineers collaborate?

12. **Interview process**
    - Glassdoor interview reviews
    - Reddit threads about interviewing there
    - Number of rounds, types of interviews

13. **Remote work reality**
    - Fully remote vs "remote-first" vs hybrid theater
    - Time zone expectations
    - Office presence requirements

## Research Commands

Use extraction commands instead of manual browsing. These return ~100 tokens of structured JSON instead of 5000+ tokens of page content.

| Source | Command | Returns |
|--------|---------|---------|
| Glassdoor | `jbs research glassdoor <url>` | Rating, reviews, pros/cons, CEO approval, interview info |
| Crunchbase | `jbs research crunchbase <url>` | Funding, stage, investors, employees, HQ |
| G2 | `jbs research g2 <url>` | Rating, reviews, pros/cons, ranking, alternatives |
| LinkedIn | `jbs research linkedin <url>` | Employees, HQ, industry, founded, specialties |

If CAPTCHA appears, solve it in the browser window that opens.

**Example output:**
```json
{"source": "glassdoor", "rating": 4.2, "reviews": 847, "pros": [...], "cons": [...]}
```

## Research Sources

Search broadly. These are starting points, not limits:

| Type | Examples |
|------|----------|
| Funding/financials | Crunchbase, Growjo, PitchBook, company IR pages, news |
| Employee sentiment | Glassdoor, Blind, LinkedIn, Reddit (r/cscareerquestions, company subreddits) |
| Customer reviews | G2, TrustRadius, Capterra, Reddit, Twitter/X, Hacker News |
| Product feedback | Reddit, Product Hunt, App Store reviews, support forums |
| News/analysis | TechCrunch, The Information, industry blogs, press releases |
| Competitive intel | G2 comparisons, Reddit threads, analyst reports |

**Reddit is especially valuable** for unfiltered product feedback and employee experiences. Search `site:reddit.com "[company name]"` or `site:reddit.com "[product name] review"`.

## Field Standards

### Company Research

| Field | Standard | Example |
|-------|----------|---------|
| `company_stage` | Stage + funding + revenue with citation | "Series C, $85M raised ([Crunchbase](url)). $45M ARR ([TechCrunch Jan 2025](url))" |
| `company_product` | What they sell + who buys it | "AI document extraction for legal. Enterprise SaaS, 200+ customers." |
| `company_size` | Headcount with source | "~400 employees ([LinkedIn](url)), grown 50% YoY" |

### Sentiment Research

Itemized findings with sentiment indicators. Each item: `{"finding": "...", "sentiment": "positive|negative|neutral"}`

| Field | Format |
|-------|--------|
| `employee_sentiment` | `[{"finding": "[Glassdoor 3.8/5](url)", "sentiment": "positive"}, {"finding": "PM turnover concerns ([review](url))", "sentiment": "negative"}]` |
| `customer_sentiment` | `[{"finding": "[G2 4.5/5](url)", "sentiment": "positive"}, {"finding": "Pricing complaints ([thread](url))", "sentiment": "negative"}]` |

### Role Research

| Field | Standard | Example |
|-------|----------|---------|
| `role_scope` | Extracted from JD: what you own, who you report to | "Staff PM for extraction pipeline. Reports to VP Product. Own ML integration roadmap." |
| `role_team` | Team structure if mentioned | "3 engineers, 1 designer. Cross-functional with ML team." |

### Context Research

Itemized findings with sentiment indicators. Each item: `{"finding": "...", "sentiment": "positive|negative|neutral"}`

| Field | Format |
|-------|--------|
| `market_context` | `[{"finding": "Market leader in legal vertical", "sentiment": "positive"}, {"finding": "Heavy competition from Docugami", "sentiment": "negative"}]` |
| `interview_process` | `[{"finding": "[5 rounds, includes case study](url)", "sentiment": "neutral"}, {"finding": "'Intense but fair' ([review](url))", "sentiment": "positive"}]` |
| `remote_reality` | `[{"finding": "Core hours 9-5 CET required ([review](url))", "sentiment": "negative"}, {"finding": "No office visits required", "sentiment": "positive"}]` |

### Analysis

| Field | Standard | Example |
|-------|----------|---------|
| `posting_analysis` | **JD language analysis ONLY.** Count patterns, identify red flags, infer role reality from wording. | "'ship' 3x, 'own' 2x, 'governance' 0x, 'stakeholder alignment' 2x. Red flag: 'influence without authority'. Team mgmt primary, IC work secondary." |
| `fit_explanation` | Connect to user's profile stories | "[User's product] maps to ML pipeline ownership. [Previous scale] relevant to 200+ enterprise customers." |

### Conclusions

**No new information here.** Synthesize what's salient from previous sections.

| Field | Standard |
|-------|----------|
| `fit_score` | 1-10 based on: level match + AI focus + location + company quality + role clarity |
| `attractions` | 3-5 positives **already identified in research above** |
| `concerns` | Gaps or risks **already identified in research above** |
| `verdict` | Pursue (strong fit) / Maybe (worth exploring) / Skip (dealbreaker found) |
| `next_steps` | Concrete actions if Pursue/Maybe |

If you're tempted to add something new in conclusions, it belongs in a research section instead.

## Verdict Guidelines

| Verdict | When |
|---------|------|
| **Pursue** | Right level + AI/ML focus + EU remote + solid company + clear scope |
| **Maybe** | Good company but unclear scope, or right role but location concerns |
| **Skip** | US/UK only, wrong domain, culture red flags, governance-heavy |

## Every Claim Needs a Source

Use markdown links to sources. Quote the specific text that supports the claim.

**Do:**
- "FY25 revenue $777M ([Prosus annual report](https://prosus.com/...))"
- "Series B, $45M led by Sequoia ([Crunchbase](https://crunchbase.com/organization/acme))"
- "3.5 stars on Glassdoor ([87 reviews](https://glassdoor.com/Reviews/acme))"
- "Customers praise ease of use but complain about pricing ([G2](https://g2.com/products/acme/reviews))"

**For job descriptions:** Don't just link to "LinkedIn JD" — quote the specific paragraph:

> "You'll own the ML pipeline end-to-end, from data ingestion to model deployment" ([JD](https://linkedin.com/jobs/...))

This lets the user verify the claim without re-reading the entire JD.

**Don't:**
- "~$800M revenue" (unsourced)
- "Well-funded" (vague)
- "Good reviews" (unquantified)
- "Employees seem happy" (no link)
- "JD mentions ownership" (quote the actual text)

## Command

For complex values with quotes and markdown links, write JSON to a temp file:

```json
// /tmp/dive.json
{
  "company_stage": "Series C, $85M ([Crunchbase](url)). $45M ARR ([TechCrunch](url)).",
  "company_product": "AI document extraction for legal. Enterprise SaaS.",
  "company_size": "~400 employees ([LinkedIn](url)), grown 50% YoY",
  "employee_sentiment": [
    {"finding": "[Glassdoor 3.8/5](url)", "sentiment": "positive"},
    {"finding": "Praise for eng culture ([review](url))", "sentiment": "positive"},
    {"finding": "Concerns about PM churn ([thread](url))", "sentiment": "negative"}
  ],
  "customer_sentiment": [
    {"finding": "[G2 4.5/5](url)", "sentiment": "positive"},
    {"finding": "Praised: API quality", "sentiment": "positive"},
    {"finding": "Criticized: pricing ([review](url))", "sentiment": "negative"}
  ],
  "role_scope": "Staff PM for extraction pipeline. Own ML integration.",
  "role_team": "3 engineers, 1 designer. Cross-functional with ML team.",
  "market_context": [
    {"finding": "Market leader in legal vertical", "sentiment": "positive"},
    {"finding": "Competes with Docugami, Eigen", "sentiment": "neutral"}
  ],
  "interview_process": [
    {"finding": "[5 rounds, includes product case study](url)", "sentiment": "neutral"}
  ],
  "remote_reality": [
    {"finding": "Core hours 9-5 CET mentioned ([review](url))", "sentiment": "negative"}
  ],
  "posting_analysis": "'ship' 3x, 'own' 2x, 'governance' 0x. Execution-heavy.",
  "fit_explanation": "[User's product] maps to ML pipeline ownership.",
  "fit_score": 8,
  "attractions": ["Direct AI ownership", "Execution culture", "EU remote"],
  "concerns": ["Legal domain learning curve"],
  "verdict": "Pursue",
  "next_steps": ["Apply via LinkedIn", "Prep strongest story"]
}
```

Then:

```bash
jbs dive <job_id> --file /tmp/dive.json
```

For simple dives, key=value syntax still works:

```bash
jbs dive li_123 fit_score=5 verdict=Skip
```
