## Things to take care of later

- Enhancing topic -> query conversions for Product Hunt APIs
- Better logic to split queries as topics to avoid diverging to broader topics

## Initial Setup:

- Created relevant documents for a well planned and guided coding session - docs/project_brief.md, docs/AGENTS.md, docs/PLAN.md
- Setup entry script with env.
- Setup pipeline as a uv-managed project

## Sourcing

- Established connectivity with openai's apis using basic langchain_openai library to chat.

- Came down to 2 possible primary sources, Hacker News and Product Hunt. Finalized on Product Hunt to start with due to well
  managed API responses which only return startup post details and no noise or garbage. They have well managed founder details,
  their contacts, websites, socials and startup's domains. Have kept Hacker News in the future pipeline as per feasibility and time. They provide more rich query based search over the news articles compared to Product Hunt.

- Used budget model gpt-4o-mini for fetching suitable queries out of input topic for Product Hunt. Provided some sample query suggestions based on sample Product Hunt responses. Added sample to project for reference.

- Sourcing from primary - Product Hunt (150+ startups per topic input)
    1. User gives an investment topic (e.g. "Voice AI Agents").
    2. LLM turns that topic into 5 short search phrases, written like real Product Hunt topic names.
    3. For each phrase, search Product Hunt's topic list. If the whole phrase finds nothing, try each word in it on its own instead.
    4. For every topic that matches, pull its top posts (20 each) from Product Hunt (graphql).
       Remove duplicate topics and duplicate posts, then save everything into candidates.json.

- PH returns 150+ raw results per topic query, too many to run full analysis on, and most are irrelevant or low-signal. Added a two-pass funnel instead of scoring everything:
    1. Drop below a minimum traction floor (votes_count < 20) - too little signal to be worth scoring either way.
    2. Leyword pre-filter: does topics overlap with thesis niche keywords? Rule-based -> gets ~150 down to ~40-60.
    3. One cheap batched LLM call (name + tagline only, yes/no against thesis) as a relevance gate -> gets ~40-60 down upto ~20-25.

- Tried to fetch further data from Hacker News, YC, github, personal websites related but failed due to scraping limitations, blockers and time constraints. Relying on PH data for analysis.

## Analysis

### What we score, and where each comes from

1. **Traction** — how many PH votes a startup got, compared to others in
   the same shortlist. Pure math, no AI involved.

2. **Product Specificity** — does the startup clearly explain what it does,
   who it's for, and how it works? Or is it vague marketing talk?
   Judged by AI, reading only the tagline + description.

3. **Differentiation** — does it explain why it's better/different from
   alternatives, or is it just generic buzzwords?
   Judged by AI, same tagline + description text.

4. **Market Fit** — does it actually match the niche we're looking for
   (our thesis), based on tagline, description, and category tags?
   Judged by AI.

### How each is scored

- Traction: math formula (min-max), gives a 0-100 number based on where
  it ranks compared to the rest of the shortlist.
- The other 3: AI picks one of 5 labels (very weak, weak, moderate,
  strong, very strong) for each, with a reason. We convert each label
  to a fixed number (10 / 30 / 50 / 75 / 95) in code — AI never picks
  the number directly, so scores stay consistent.

### Final score

We combine all 4 into one number using weights (how much each one
counts):

- Product Specificity: 35%
- Differentiation: 25%
- Traction: 25%
- Market Fit: 15%

(Specificity and differentiation count the most because they tell us
most about whether it's a real, focused product. Traction is real
behavior data but noisy. Market fit is more of a relevance check than
a quality signal.)

### What we dropped, and why

- **Team background** — almost never available from our free data
  sources, so we stopped trying to score it and just note the
  limitation once instead of chasing it per candidate.
- **Recency** — our shortlist ends up mostly 1 week - 1 month old
  anyway, so scoring "how fresh" didn't actually tell us anything
  useful. Dropped it and gave its weight to the two criteria that
  do discriminate.

### Final call

- 70+ → Take a meeting
- 45-69 → Watch
- below 45 → Pass

### Enhancements

- Enhanced the prompt to extract would change mind reasoning for each scoring criteria. Will be later used to generate memo content
