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
