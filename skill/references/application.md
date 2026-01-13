# Application Prep Standards

**Goal:** Give user a concrete to-do list, not a black hole. Squeeze every drop of opportunity.

Read before preparing:
- `data/profile/base.md` — CV content, experience
- `data/profile/star-bank.md` — Interview stories
- `data/profile/anti-positioning.md` — Red flags, phrases to avoid
- The deep dive for this job (company research, product intel)

## Workflow

1. `jbs apply <job_id>` — Creates application record, returns `app_id`
2. Generate ALL sections below (don't upload yet)
3. Write everything to `/tmp/app.json`
4. Upload once: `jbs app update <app_id> --file /tmp/app.json`

**DO NOT** upload sections incrementally.
**DO NOT** curl the API directly — use `jbs` CLI only.

## Schema Reference

Use these **exact field names** in your JSON:

| Field | Type | Structure |
|-------|------|-----------|
| `cv_tailored` | string | Markdown |
| `cover_letter` | string | Markdown |
| `gap_analysis` | object | `{matches: [], partial_matches: [], gaps: [], missing_stories: []}` |
| `referral_search` | object | `{contacts: [], channel_priority: []}` |
| `salary_research` | object | `{range: "", glassdoor: "", anchoring_strategy: ""}` |
| `interview_prep` | object | `{what_to_say: [], what_not_to_say: [], questions_to_ask: [], red_flags: []}` |
| `follow_up` | object | `{milestones: [], backup_contacts: []}` |

**If CLI rejects your JSON:** Check field names match this table exactly. Don't debug the backend — fix your JSON.

---

## 1. CV Optimization

**Goal:** ATS picks this CV out of hundreds.

### Process

1. **Extract JD requirements** — List every skill, keyword, qualification mentioned
2. **Map to user's experience** — Find matches in base.md and star-bank.md
3. **Mirror keywords exactly** — If JD says "cross-functional collaboration", CV says "cross-functional collaboration" (not "worked with other teams")
4. **Quantify everything** — Numbers get attention: "70M MAU", "3 months", "$45M ARR"

### Drill the User

If STAR bank doesn't cover a JD requirement:

> "The JD emphasizes [X]. Do you have experience with [X] that's not in your STAR bank? Even adjacent experience counts. For example:
> - Have you done something similar in a different context?
> - Have you learned about [X] even if you haven't done it professionally?
> - Can we frame existing experience to highlight [X] aspects?"

**Don't accept "no" too easily.** Users undervalue their experience. Probe deeper.

### CV Structure

- **2 pages max** — Recruiters skim
- **Summary** — 3 lines, mirrors JD language, includes key numbers
- **Experience** — Reverse chronological, 3-5 bullets per role with metrics
- **Skills section** — Mirror JD keywords exactly

### Avoid (from anti-positioning.md)

- "Managed a team of X" → "Shipped [product] with cross-functional team"
- "Oversaw strategy" → "Owned [product] from concept to launch"
- "Coordinated stakeholders" → "Delivered [outcome]"
- Never: governance, advisory, strategic liaison

---

## 2. Gap Analysis

**Goal:** Find every angle to position the user. Be ruthlessly honest about gaps.

### Process

1. **List JD requirements** — Every stated and implied requirement
2. **Rate each** — Strong match / Partial match / Gap / Can learn
3. **Find positioning angles** — How to frame partial matches as strengths
4. **Identify story gaps** — Which STAR stories are missing?

### Output Structure

```markdown
## Matches (lead with these)
- [Requirement]: [Evidence from profile] — [How to emphasize]

## Partial Matches (frame carefully)
- [Requirement]: [Adjacent experience] — [How to position]

## Gaps (address proactively)
- [Requirement]: [Gap] — [Mitigation: learning plan, transferable skills, honest acknowledgment]

## Missing Stories (drill the user)
- [Requirement]: Need STAR story for [X]. Ask user: "[specific probing question]"
```

### Squeeze Every Drop

For each gap, ask:
- Is there adjacent experience we're not considering?
- Can we frame this as "eager to learn" with evidence of fast learning?
- Is this a hard requirement or nice-to-have?
- Can we preempt this in cover letter?

---

## 3. Cover Letter

**Goal:** Personalized to this company, not a template.

### Structure (4 paragraphs, 250 words max)

**Para 1 — Hook (1 sentence):**
Immediately relevant accomplishment that maps to their need.
> "I took [Current Company]'s [Product] from concept to beta in 3 months—exactly the zero-to-one execution [Company] needs for [specific product/challenge from research]."

**Para 2 — Evidence (2-3 sentences):**
Connect strongest STAR stories to their specific challenges (from deep dive research).
> "At [Previous Company], I grew [metric] by [action]. At [Current Company], I'm applying the same approach to [current work]. Your [specific product challenge from research] is the same pattern."

**Para 3 — Why This Company (2-3 sentences):**
Prove you researched them. Reference specific product, mission, challenge.
> "I've followed [Company]'s approach to [specific thing from research]. The [specific challenge/opportunity] aligns with my experience in [relevant area]. I'm particularly drawn to [specific authentic reason]."

**Para 4 — Close (1-2 sentences):**
Clear ask, confident but not arrogant.
> "I'd welcome the chance to discuss how my [specific skill] can accelerate [their specific goal]. Available at your convenience."

### Personalization Checklist

- [ ] Company name appears (not just "your company")
- [ ] Specific product/feature mentioned
- [ ] Challenge from deep dive research referenced
- [ ] Why THIS company, not just "a company like this"
- [ ] No template language ("I am excited to apply for...")

---

## 4. Application Channel

**Goal:** Maximize response rate. Referral >> everything else.

### Referral Hunting

1. **Search LinkedIn** — 1st connections at company
2. **Search 2nd connections** — Ask mutual connection for intro
3. **Search alumni networks** — Same school, same previous company
4. **Ask user directly** — "Do you know anyone at [Company] or who used to work there?"

If referral found:
> "Found [Name], [Role] at [Company]. They're a [1st/2nd] connection via [mutual]. Suggested message: [draft]"

### Channel Priority

1. **Referral** — 10x response rate
2. **Direct to hiring manager** — Find on LinkedIn, personalized message
3. **Recruiter** — If listed in JD
4. **Company careers page** — With tailored materials
5. **LinkedIn Easy Apply** — Last resort, low signal

### Application Tracking

- Date applied
- Channel used
- Contact person
- Follow-up dates

---

## 5. Salary Intelligence

**Goal:** Know the range before they ask. Anchor high.

### Research

- Glassdoor salary data for role + location
- Levels.fyi (especially for tech companies)
- Blind salary threads
- LinkedIn salary insights
- Ask in referral conversation (if warm enough)

### Output

```markdown
## Salary Range
- Glassdoor: [range] ([N] data points)
- Levels.fyi: [range] (if available)
- Blind: [range] (if threads found)
- **Estimated range:** [low] - [mid] - [high]

## Anchoring Strategy
- User's minimum: [from anti-positioning.md]
- Recommended anchor: [high end of range]
- Negotiation leverage: [specific strengths to emphasize]
```

---

## 6. Interview Prep

**Goal:** Homework for the user. Concrete, actionable.

### What to Say

Map STAR stories to likely questions:

| Likely Question | STAR Story | Key Point | Practice This |
|-----------------|------------|-----------|---------------|
| "Tell me about yourself" | — | 90-sec pitch ending with [most relevant story] | Write it out, time it |
| "Why this role?" | — | [Specific connection to their product] | Reference deep dive research |
| "[JD requirement]" | [Story] | [Key metric] | Practice out loud |

### What NOT to Say

From anti-positioning.md + gap analysis:

| Topic | Don't Say | Say Instead |
|-------|-----------|-------------|
| [Topic from anti-positioning] | [Phrase to avoid] | [Alternative framing] |
| [Gap identified] | [Don't oversell] | [Honest acknowledgment + mitigation] |

### Questions to Ask Them

Prioritized by signal value:

1. "What does success look like in the first 6 months?" — Reveals expectations
2. "What's the biggest challenge the PM team faces?" — Reveals problems
3. "How are product decisions made?" — Detects governance culture
4. "What shipped recently that you're proud of?" — Reveals execution culture
5. "Why is this role open?" — Growth vs backfill vs reorg

### Questions to Prepare For

Based on JD + gap analysis:

| Question | Why They'll Ask | Prepared Answer | Red Flags in Their Response |
|----------|-----------------|-----------------|----------------------------|
| [Predicted question] | [JD requirement it maps to] | [STAR story + key point] | [What bad answer from them looks like] |

### Red Flags to Watch

During interview, watch for:

- "Stakeholder alignment" emphasized repeatedly
- Vague answers about decision-making process
- Can't name recent shipped features
- "We're still figuring out the PM role"
- Interviewer badmouths other teams
- Excessive focus on process over outcomes

---

## 7. Case Study / Product Exercise Prep

**Goal:** If PM role, expect product exercise. Prepare the framework.

### Common Formats

- **Product sense** — "How would you improve [product]?"
- **Metrics** — "How would you measure success of [feature]?"
- **Prioritization** — "Given these 5 features, how would you prioritize?"
- **Strategy** — "Where should [product] go in 3 years?"
- **Estimation** — "How many X are there in Y?"

### Prep Work

1. **Research their product deeply** — Use it, read reviews, understand pain points
2. **Prepare frameworks** — RICE, impact/effort, user journey
3. **Have opinions** — "If I were PM of [their product], I'd focus on [X] because [Y]"
4. **Practice out loud** — Structure matters as much as content

---

## 8. Follow-up Timeline

**Goal:** Don't ghost or be ghosted.

| Milestone | Timeline | Action |
|-----------|----------|--------|
| After applying | +1 week | Follow up if no response |
| After phone screen | +3 days | Thank you note + reiterate interest |
| After onsite | +1 day | Thank you to each interviewer |
| After final round | +1 week | Check in on timeline |
| If ghosted | +2 weeks | Try backup contact |

### Backup Contacts

If primary recruiter/contact ghosts:
- Other recruiters at company (LinkedIn)
- Hiring manager directly
- Referral contact (if used)
- Other team members you interviewed with

---

## Command

```bash
# Start application (creates record, returns app_id)
jbs apply <job_id>

# Update application fields via JSON file
jbs app update <app_id> --file /tmp/app.json
```

Write all application prep to a JSON file:

```json
// /tmp/app.json
{
  "cv_tailored": "# [Your Name]\n\n## Summary\nSenior PM with 10+ years...",
  "cover_letter": "Dear Hiring Manager,\n\nI took [Product] from concept to beta...",
  "gap_analysis": {
    "matches": ["AI product experience", "Enterprise scale"],
    "partial_matches": ["Legal domain - adjacent via compliance work"],
    "gaps": ["No direct legal tech experience"],
    "missing_stories": ["Ask user about compliance/regulatory experience"]
  },
  "interview_prep": {
    "what_to_say": [
      {"question": "Tell me about yourself", "answer": "90-sec pitch ending with strongest story"}
    ],
    "what_not_to_say": ["Don't mention governance experience"],
    "questions_to_ask": ["What does success look like in 6 months?"],
    "red_flags": ["If they emphasize 'stakeholder alignment' heavily"]
  },
  "salary_research": {
    "range": "€90-120k",
    "glassdoor": "€95k median for Staff PM",
    "anchoring_strategy": "Anchor at €115k, accept €100k"
  },
  "referral_search": {
    "contacts": ["John Doe - 2nd connection via Jane"],
    "channel_priority": ["Referral", "Direct to HM", "LinkedIn"]
  },
  "follow_up": {
    "milestones": ["Apply: +1 week follow-up", "Phone screen: +3 days thank you"],
    "backup_contacts": ["Recruiter on LinkedIn"]
  }
}
```
