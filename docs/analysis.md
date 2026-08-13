You should not rate startups based only on Hacker News articles. That would be a weak reading of the assignment, and it would not support a credible Team, Product, Market, and Risk analysis.

The assignment only asks for at least one freshness or traction signal. Hacker News can satisfy that signal, but it is not supposed to carry the full investment judgment. In your own brief, the intended shape is already closer to the right answer: Product Hunt or HN for discovery, then the company’s own website and optionally GitHub for enrichment in `project_brief.md:25` and `project_brief.md:39`.

The practical interpretation is:

1. Use one discovery source deeply.
2. Use one enrichment source deeply.
3. Use HN only as a traction input when available.

A strong version for this assignment is:

1. Product Hunt for discovery and freshness
2. Company website plus linked GitHub for analysis

That is enough to satisfy the prompt much more cleanly than trying to force everything through HN.

What HN is actually good for:

- recent visibility
- points
- number of comments
- whether technical users are discussing it
- rough recency of public attention

What HN is not good for:

- founder background
- prior exits
- actual product details beyond the linked page
- market structure
- investment-quality risk analysis

So your score should not be “based on HN.” HN should be one small sub-signal inside a broader scoring rubric.

A defensible thesis could be:

High-potential AI infrastructure and workflow startups for technical teams, where I favor products that solve a painful, repeatable workflow, show credible technical depth, and have some evidence of market pull or developer adoption.

Then score against 4 or 5 criteria like this:

- Problem clarity and urgency: 0 to 25
- Product differentiation and technical depth: 0 to 25
- Team credibility signal: 0 to 20
- Market pull / traction signal: 0 to 20
- Execution maturity / trustworthiness: 0 to 10

How each one gets evidence:

- Problem clarity and urgency: tagline, description, homepage copy
- Product differentiation and technical depth: homepage, docs, GitHub if linked
- Team credibility signal: makers, about page, explicit founder bios if available
- Market pull / traction signal: Product Hunt votes and recency, HN points/comments if there is a real match, GitHub activity if open source
- Execution maturity / trustworthiness: docs, pricing, security page, repo quality, clear positioning

This is the key point: if founder data is missing, you do not invent it. You score Team as unknown or partial and lower data completeness. The assignment does not require complete knowledge; it requires structured judgment with explicit open questions.

A good evidence policy would be:

- Product Hunt gives:
    - name
    - launch recency
    - votes
    - short product description
    - maker handles
    - whether GitHub or LinkedIn links exist

- Company website gives:
    - plain-language product explanation
    - ICP and use case
    - market clues
    - pricing and maturity clues
    - team/about information if present

- GitHub gives, when linked:
    - technical depth signal
    - repo activity
    - stars and recency
    - whether the company is genuinely shipping technical product

- HN gives, when matched by company name or domain:
    - one traction signal only

So a startup can be rated credibly like this:

- Team: weak / medium / strong evidence depending on whether founders are named, bios exist, and technical background is visible
- Product: usually strongest section, based on site and launch copy
- Market: inferred from category, buyer, pain point, and competitors mentioned on site
- Risks: derived from what is missing or unproven
- Score: deterministic weighted average of the above, with missing-data penalties or incomplete criteria

Example of how HN should be used:

- “This company launched recently and has 600 Product Hunt votes”
- or “HN thread has 300 points and 120 comments”
- or “No HN discussion found”

That is enough. You do not need HN articles to tell you whether the startup is good. You only need one freshness or traction signal, and HN is one optional source for that.

If I were doing this assignment, I would explicitly write the method like this:

I am not using Hacker News as the main analytical source. I use it only as an optional traction signal. My primary evidence comes from Product Hunt launch metadata, the startup’s own website, and linked GitHub presence where available. When founder or market data is not directly supported by source material, I mark it as unknown and surface it as an open question rather than guessing.

That is defensible and aligned with the assignment.

A clean implementation choice would be:

1. Source with Product Hunt
2. Enrich with website and GitHub
3. Use HN only if a company-name or domain search finds a clear match
4. Cap recommendations at Watch when team or market evidence is too thin

If you want, I can next give you:

1. a concrete scoring rubric with weights and null-handling
2. a minimal evidence schema for candidates.json and analysis.json
3. a recommendation on whether to choose Product Hunt plus website or YC batch plus website for the assignment

---

Updated todo list

Use the website as an evidence source, not as something you need to fully “understand” page by page. Different formats are manageable if you keep the crawler shallow, heuristic-driven, and tolerant of failure.

For websites, I would use a layered approach:

1. Resolve the canonical URL from the Product Hunt link.
2. Fetch the homepage with `httpx`, following redirects and recording final URL, status code, and fetch errors.
3. Extract cheap, format-agnostic signals first:
    - `<title>`
    - meta description
    - Open Graph tags
    - main headings like `h1` and `h2`
    - visible body text after stripping nav/footer noise
4. From the homepage, follow only a few high-value links based on text or URL patterns:
    - `about`
    - `team`
    - `company`
    - `careers`
    - `pricing`
    - `docs`
    - `security`
    - `customers`
5. Limit each company to maybe 3 to 5 pages total, then stop.

That works because most of the information you need is broad and repetitive across sites even if HTML structure differs. You are not trying to scrape every field from arbitrary DOMs. You are trying to collect a compact evidence bundle.

A good website pipeline usually looks like this:

- `fetch`: URL, status, final URL, content type
- `clean`: remove scripts/styles/nav boilerplate
- `extract`: title, headings, paragraphs, candidate links
- `classify`: homepage / about / pricing / docs / blog
- `summarize`: store a short normalized text block per page
- `cite`: keep source URL for every extracted fact

The important design choice is to degrade gracefully. If a site is inaccessible, JS-heavy, rate-limited, or just messy, you should not fail the startup. You should record:

- `website_fetch_status = blocked | timeout | partial | success`
- `founder_data = null`
- `market_evidence = partial`
- `open_questions += ["Could not access team/about information from public website"]`

That is much better than trying to force unreliable scraping.

What usually breaks website fetching:

- JS-rendered sites with little server-rendered text
- bot protection / 403 / 429
- very noisy marketing sites
- weird redirects
- PDFs or app-first sites

How to handle that in v1:

- use plain `httpx` + `BeautifulSoup`, not a headless browser
- set a user-agent, timeout, retry, and redirect-following
- skip sites that fail after a couple tries
- mark the evidence as missing, not fatal
- don’t try to beat anti-bot protections

That is enough for the assignment. A headless browser is overkill unless too many shortlisted sites are unreadable.

On GitHub: the public APIs are actually useful even on the free/public side, as long as the repo/org/user is public. You do not need special access to read public repository metadata.

For a public repo, GitHub’s public API can give you things like:

- repo name and owner
- description
- homepage URL
- primary language
- topics
- stars
- forks
- watchers
- open issues count
- created and updated timestamps
- pushed-at timestamp
- default branch
- license
- archived / disabled status
- visibility
- contributor stats in some cases
- releases and tags
- recent commits
- org/user profile bio and company/homepage fields

For your assignment, the most useful repo-level signals are:

- `updated_at` or `pushed_at`: is it active
- `stargazers_count`: rough public interest
- `language` and topics: technical shape
- repo description and homepage: product alignment
- org profile URL: whether it matches the company domain
- presence of docs, releases, examples, SDKs, or API repos

What GitHub can help you infer:

- technical depth signal
- open-source posture
- engineering maturity signal
- whether the product claims match actual public artifacts
- whether development appears active

What GitHub cannot reliably tell you:

- revenue
- customer traction
- founder quality unless the founder profile is explicitly linked and clearly matched
- enterprise adoption
- moat on its own

A minimal GitHub enrichment record might include:

```python
{
  "github_url": "...",
  "kind": "org" | "repo" | "user",
  "bio": "...",
  "company": "...",
  "blog": "...",
  "public_repos": 12,
  "followers": 80,
  "repo_name": "...",
  "description": "...",
  "language": "TypeScript",
  "topics": ["ai", "agents", "workflow"],
  "stars": 420,
  "forks": 31,
  "created_at": "...",
  "updated_at": "...",
  "pushed_at": "..."
}
```

For this project, I would use GitHub only when:

- Product Hunt explicitly gives a GitHub link in `product_links`
- or the company website explicitly links to a GitHub org/repo

That keeps matching clean and defensible.

So the practical recommendation is:

- websites are messy, but a shallow multi-page fetch with heuristics is feasible
- GitHub public API is very useful for public technical signal
- neither source needs to be perfect
- missing or blocked data should lower completeness, not break the pipeline

If you want, I can next give you:

1. the exact website-fetch heuristics and page selection rules
2. the exact GitHub fields worth storing in `candidates.json`
3. a null-safe scoring design that uses website + GitHub + Product Hunt without overclaiming
