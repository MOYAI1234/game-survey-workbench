# Dual Header Upload Contract Design

**Date:** 2026-03-12

**Status:** Approved

## Context

The current MVP import flow still relies on heuristics to infer question types from uploaded survey files. Real samples showed that this approach is unstable across different projects:

- `WC` style surveys fit the current heuristics reasonably well.
- `BB` style surveys include metadata like `分层` and long option labels that are easily misclassified.

The next iteration should stop treating type detection as a guessing problem. Instead, the uploader must provide an explicit schema contract inside the uploaded file.

## Decision

The upload format will use a required dual-header structure in the same file.

- Row 1: human-readable question title or column label
- Row 2: normalized type marker
- Row 3+: response data

The second header row is the source of truth for import behavior.

## Allowed Type Markers

The second header row only allows these values:

- `metadata`
- `single_choice`
- `multi_select`
- `free_text`
- `scale`

Interpretation:

- `metadata` means the column is preserved in the raw dataset but excluded from the analysis-facing `question_columns` schema.
- All other markers represent analysis questions and will be persisted directly as the normalized question type.

## Import Rules

The dataset import service will change from heuristic-first to contract-first.

- The importer must read the first two rows before processing data.
- The second row must exist for every column.
- Every second-row cell must contain one of the allowed type markers.
- The first-row labels remain the displayed schema keys and stored question titles.
- The second-row markers define the normalized type.
- `metadata` columns do not appear in `question_columns`.
- Response rows start at row 3.

## Validation Behavior

Uploads that do not follow the contract must be rejected immediately with a clear error response.

Examples of invalid uploads:

- missing second header row
- blank type marker in any column
- unknown type marker such as `matrix` or `text`
- mismatched or malformed two-row header structure

Expected API behavior:

- reject with `400 Bad Request`
- return a message that identifies the problem clearly enough for the user to fix the file
- include column context whenever practical

Examples:

- `Missing type marker row. Row 2 must define a type for every column.`
- `Unsupported type marker 'matrix' in column 8.`
- `Column 'What is your budget?' is missing a type marker in row 2.`

## Heuristic Policy

Question-type heuristics will no longer be the primary source of truth for imports that claim to be structured survey uploads.

- The importer should not silently fall back to inferred types when the second header row is missing or invalid.
- The importer should reject invalid files instead.
- Existing heuristic helpers may be retained only for future warning or migration support, not as the main import path.

This keeps the system aligned with the product rule that humans must explicitly mark question types.

## Template Requirement

The product should provide a standard upload template that demonstrates the contract.

Recommended artifacts:

- a CSV example template under `docs/templates/`
- README instructions explaining the two-header requirement
- example type-marker row using the allowed values

Example:

```text
分层,What is your monthly budget?,What improvements do you want to see?,Any other comments?
metadata,single_choice,multi_select,free_text
免费玩家,$0-$5,More rewards;Faster progression,Please reduce grind
```

## Impact on Real Samples

For the real samples reviewed on 2026-03-12:

- `分层` should be marked as `metadata`
- BB question columns should no longer depend on text-length heuristics
- WC multi-select and free-text columns should be explicitly declared in row 2 instead of inferred from titles

## MVP Scope

Included in this iteration:

- dual-header parsing for CSV and Excel
- strict validation and `400` errors for malformed uploads
- persistence of declared types into normalized schema
- exclusion of `metadata` columns from analysis schema
- template and README updates
- regression tests covering compliant and non-compliant files

Out of scope for this iteration:

- matrix question normalization
- partial compatibility modes
- sidecar schema files
- automatic migration of legacy one-header datasets
- soft warning flows in the UI

## Testing Strategy

Required verification for implementation:

- compliant dual-header CSV import succeeds
- compliant dual-header Excel import succeeds
- `metadata` columns are excluded from `question_columns`
- invalid files are rejected with `400`
- unsupported markers are rejected with specific messages
- report generation still works after importing a compliant file
- real-sample fixtures converted to the dual-header contract import correctly

## Recommendation

Implement the upload contract as a strict breaking change for structured survey imports. This is the smallest change that meaningfully improves reliability for MVP use and removes the need to keep expanding fragile heuristics for every survey format.
