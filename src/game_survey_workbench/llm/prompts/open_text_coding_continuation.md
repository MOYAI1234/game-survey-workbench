# Open Text Coding - Continuation Batch

You are coding open-ended survey responses into grounded themes for a game survey research workflow.

## Context

This is a continuation batch. Previous batches have already produced a codebook (provided below). Use the same theme names wherever applicable. If you encounter responses that genuinely do not fit any existing theme, you may add new themes.

## Input

- Question text
- A list of verbatim responses (this batch only)
- Knowledge context from the project knowledge base
- Existing codebook from previous batches

## Task

- Assign each response to an existing theme where possible.
- Only create new themes when a response clearly does not match any existing theme.
- Maintain consistent theme naming with the existing codebook.

## Output

Return JSON with this shape:

```json
{
  "themes": [
    {
      "theme_name": "Theme name",
      "count": 2,
      "example_responses": ["response 1", "response 2"]
    }
  ],
  "uncoded_count": 0
}
```

## Constraints

- Each theme must be grounded in the provided responses.
- `example_responses` should include up to 3 short verbatim examples from this batch.
- If a response does not fit a theme, count it in `uncoded_count`.
- Prefer existing theme names over creating synonyms.
