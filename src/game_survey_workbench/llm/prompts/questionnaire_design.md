# Questionnaire Design Prompt

Use the supplied project context, research goal, hypotheses, and knowledge snippets
to draft a Markdown questionnaire spec that remains easy to edit manually.

## Output Structure

Organize the questionnaire into clear thematic sections. Each section should:

1. State a brief **section rationale** - why this group of questions matters to the research goal.
2. List 2-5 questions per section.
3. For each question, add a one-line **diagnostic note** explaining what the question is designed to reveal and how a researcher should read the answers.

## Segmentation Awareness

- If the knowledge or hypotheses mention distinct player segments (e.g., payers vs. free users, new vs. returning), include at least one question that helps distinguish segment-specific experiences.
- Where a follow-up or branching question would improve segment clarity, note it explicitly.

## Question Quality

- Keep questions aligned with the stated research goal and hypotheses.
- Prefer concrete, behavioral wording over vague satisfaction scales.
- Use the supplied knowledge as grounding - reference it in rationale where relevant.
- Do not invent citations or claim unsupported evidence.

## Format

- Output valid, editable Markdown.
- Use `##` for section headings, `-` for question lists, and `>` for diagnostic notes.
