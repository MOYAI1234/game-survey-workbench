from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CrosstabResult:
    row_column: str
    col_column: str
    row_values: list[str]
    col_values: list[str]
    table: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    group_summaries: dict[str, dict[str, float]] = field(default_factory=dict)
