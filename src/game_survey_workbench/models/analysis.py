from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScaleSummary:
    mean: float
    top_box_rate: float
