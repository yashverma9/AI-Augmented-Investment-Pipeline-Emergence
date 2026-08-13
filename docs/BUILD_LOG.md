## Things to take care of later

- Enhancing topic -> query conversions for Product Hunt APIs

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

- Sourcing from primary - Product Hunt
    1. User gives an investment topic (e.g. "Voice AI Agents").
    2. LLM turns that topic into 5 short search phrases, written like real Product Hunt topic names.
    3. For each phrase, search Product Hunt's topic list. If the whole phrase finds nothing, try each word in it on its own instead.
    4. For every topic that matches, pull its top posts (20 each) from Product Hunt (graphql).
       Remove duplicate topics and duplicate posts, then save everything into candidates.json.
