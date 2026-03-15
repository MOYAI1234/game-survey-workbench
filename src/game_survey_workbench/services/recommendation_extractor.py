"""Extract structured recommendations from insight narratives."""

from __future__ import annotations

import re


def extract_recommendations(narrative: str | None) -> list[str]:
    """Extract recommendation bullets from an insight narrative."""

    if not narrative:
        return []

    match = re.search(
        r"#+\s*Recommend(?:ed\s+Actions|ations)\s*\n(.*?)(?=\n#+\s|\Z)",
        narrative,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []

    section_text = match.group(1).strip()
    recommendations: list[str] = []

    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            recommendations.append(stripped[2:].strip())
            continue

        if re.match(r"^\d+\.\s", stripped):
            recommendations.append(re.sub(r"^\d+\.\s*", "", stripped).strip())

    return [recommendation for recommendation in recommendations if recommendation]
