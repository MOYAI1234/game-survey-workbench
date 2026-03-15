# Insight Synthesis Prompt

Write Markdown insight synthesis for a game survey analysis workflow.

## Input

- Research goal and objectives (from project brief)
- Statistical findings (deterministic, pre-computed)
- Cross-tabulation findings (segment-level comparisons)
- Matrix battery findings (multi-item satisfaction/rating comparisons)
- Ranking findings (item priority orderings)
- Coded open-text themes (from prior coding step)
- Retrieved knowledge snippets (from project knowledge base)

## Output Structure

### 1. Executive Takeaway (1-2 sentences)

Open with the single most important finding that a decision-maker needs to hear. Ground it in a specific stat or coded theme.

### 2. Supporting Analysis (2-4 paragraphs)

- Connect statistical findings, cross-tabulation patterns, coded themes, and knowledge where they reinforce each other.
- When cross-tab data reveals a segment gap, call out the magnitude and the affected segment explicitly.
- When matrix batteries show item-level spread, highlight the strongest and weakest items and the gap size.
- Use brief inline citations - e.g., "(per Churn Framework)" or "(coded theme: Boredom, n=12)" - rather than pasting long excerpts.
- Call out contradictions or gaps explicitly rather than ignoring them.

### 3. Recommended Actions (3-5 bullets)

- Each recommendation must be tied to a specific finding (stat, cross-tab, coded theme, or knowledge source).
- Frame recommendations as "Consider X because Y (evidence: Z)" rather than vague "improve the experience."
- Prioritize recommendations by expected impact, not by order of appearance in findings.
- Where cross-tab data shows a segment-specific problem, target the recommendation to that segment.
- Where matrix data reveals a weak item, recommend investigation or action on that specific item.

### 4. Open Questions (1-3 bullets, optional)

- Flag areas where the data is insufficient to draw a conclusion.
- Suggest follow-up research or data collection that would resolve the ambiguity.

## Constraints

- Every claim must point back to a stat finding, cross-tab pattern, coded theme, or knowledge source.
- Do not fabricate evidence.
- Keep the output in Markdown prose suitable for a report section.
- Be concise - the full narrative should fit in roughly 300-500 words.
