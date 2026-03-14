# Insight Synthesis Prompt

Write Markdown insight synthesis for a game survey analysis workflow.

## Input

- Research goal
- Statistical findings (deterministic, pre-computed)
- Coded open-text themes (from prior coding step)
- Retrieved knowledge snippets (from project knowledge base)

## Output Structure

### 1. Executive Takeaway (1-2 sentences)

Open with the single most important finding that a decision-maker needs to hear. Ground it in a specific stat or coded theme.

### 2. Supporting Analysis (2-4 paragraphs)

- Connect statistical findings, coded themes, and knowledge where they reinforce each other.
- Use brief inline citations - e.g., "(per Churn Framework)" or "(coded theme: Boredom, n=12)" - rather than pasting long excerpts.
- Call out contradictions or gaps explicitly rather than ignoring them.

### 3. Recommended Actions (2-4 bullets)

- Each recommendation should be concrete and tied to a specific finding.
- Frame recommendations as "Consider X because Y" rather than vague "improve the experience."

## Constraints

- Every claim must point back to a stat finding, coded theme, or knowledge source.
- Do not fabricate evidence.
- Keep the output in Markdown prose suitable for a report section.
- Be concise - the full narrative should fit in roughly 200-400 words.
