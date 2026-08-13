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
