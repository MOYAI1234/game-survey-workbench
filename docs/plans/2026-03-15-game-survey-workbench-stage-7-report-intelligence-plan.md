# Stage 7: Report Intelligence & Structured Research Output — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Markdown report — the core loop's final deliverable — structured, brief-aware, version-tracked, and actionable, so researchers can hand it to stakeholders without manual rewriting.

**Architecture:** Replace the single-template report render with a section-based report builder that assembles structured sections (executive summary, methodology, findings by question type, recommendations, evidence basis) from existing analysis artifacts. Inject Research Brief context into report framing. Add report versioning parallel to questionnaire versioning. No new dependencies.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLModel, pandas, pytest, httpx/TestClient (all existing). No new dependencies.

**North-star alignment:** The permanent product loop ends at `Markdown Report`. The north-star says: "Prefer work that strengthens the core loop over shell polish." Report generation is currently the weakest link — it receives rich structured input (deterministic findings, cross-tabs, coded themes, insight narrative, recommendations, knowledge snippets, brief objectives) but renders a flat document with minimal structure. This stage makes the report output worthy of the analysis pipeline that feeds it.

**Prerequisite state:** Stage 6 completed on master. Workflow state machine, questionnaire versioning, insight iteration, TF-IDF retrieval, and error feedback all operational. ~184 tests passing.

---

## Stage 6 Closeout Assessment

### What Stage 6 delivered

| Sub-stage | Capability | Status |
|-----------|-----------|--------|
| 6A | Workflow state machine (imported → coded → insights_ready → report_generated) | ✓ |
| 6B | Error feedback + workflow progress visibility on analysis dashboard | ✓ |
| 6C | Questionnaire version history, diff comparison, iterative refinement with feedback | ✓ |
| 6D | Insight re-generation with different research goals | ✓ |
| 6E | TF-IDF retrieval upgrade with CJK support | ✓ |

### What Stage 6 left unaddressed

1. **Report is still a flat template fill** — the Jinja2 template `report.md.j2` renders title + summary bullets + narrative + evidence, with no structured sections matching research practice
2. **Brief context is not used in reports** — `ResearchBriefRecord` fields (background, objectives, hypotheses, target_audience) are injected into questionnaire and insight prompts but never appear in the report itself
3. **No report versioning** — questionnaires have version history and diff, but reports are overwritten; a researcher cannot compare report iterations
4. **Recommendations are buried in narrative** — the insight prompt asks for "Recommended Actions" but they're embedded in free-text; no structured extraction or prioritized display
5. **No methodology section** — reports don't describe the sample, question types analyzed, or analytical approach used

### Why this is Stage 7, not polish

These are not formatting issues. They are **structural gaps in the final deliverable**:

- A report without methodology context is not credible for stakeholder review
- A report without structured recommendations requires manual extraction
- A report that can't be compared across iterations defeats the purpose of Stage 6's iteration infrastructure
- A report that ignores the Research Brief wastes the Stage 3 investment

### Non-goals for Stage 7

- No PDF/Word export (Markdown remains the output)
- No chart/visualization generation
- No interactive report features (stays static Markdown)
- No multi-dataset comparative reports (single analysis run per report)
- No automated quality scoring of report content
- No frontend framework change

---

## Task Breakdown

### Task 1: Report Section Registry

**Why first:** Every subsequent task (structured sections, brief injection, methodology) depends on a section-based report architecture. Currently the report is one monolithic template. This task establishes the section registry that all other tasks build on.

**Files:**
- Create: `src/game_survey_workbench/services/report_sections.py`
- Test: `tests/test_stage7a_report_sections.py`

**Step 1: Write the failing test**

```python
# tests/test_stage7a_report_sections.py
"""Report section registry and assembly."""
import pytest
from game_survey_workbench.services.report_sections import (
    ReportSection,
    ReportSectionRegistry,
    assemble_report_markdown,
)


def test_registry_returns_sections_in_order():
    registry = ReportSectionRegistry()
    registry.register(ReportSection(
        key="executive_summary",
        title="Executive Summary",
        order=10,
        content="The study found significant engagement differences.",
    ))
    registry.register(ReportSection(
        key="methodology",
        title="Methodology",
        order=20,
        content="Online survey, N=500, fielded 2026-03-01 to 2026-03-07.",
    ))
    registry.register(ReportSection(
        key="findings",
        title="Key Findings",
        order=30,
        content="- Finding 1\n- Finding 2",
    ))
    sections = registry.ordered_sections()
    assert [s.key for s in sections] == [
        "executive_summary", "methodology", "findings"
    ]


def test_assemble_produces_markdown_with_headings():
    registry = ReportSectionRegistry()
    registry.register(ReportSection(
        key="exec",
        title="Executive Summary",
        order=10,
        content="Key takeaway here.",
    ))
    registry.register(ReportSection(
        key="recs",
        title="Recommendations",
        order=20,
        content="- Do X\n- Do Y",
    ))
    md = assemble_report_markdown(
        title="Player Survey Report",
        date="2026-03-15",
        registry=registry,
    )
    assert "# Player Survey Report" in md
    assert "## Executive Summary" in md
    assert "Key takeaway here." in md
    assert "## Recommendations" in md
    assert "- Do X" in md


def test_empty_sections_are_skipped():
    registry = ReportSectionRegistry()
    registry.register(ReportSection(
        key="exec",
        title="Executive Summary",
        order=10,
        content="Summary here.",
    ))
    registry.register(ReportSection(
        key="methodology",
        title="Methodology",
        order=20,
        content="",  # empty — should be skipped
    ))
    md = assemble_report_markdown(
        title="Report",
        date="2026-03-15",
        registry=registry,
    )
    assert "## Executive Summary" in md
    assert "## Methodology" not in md


def test_duplicate_key_replaces_previous():
    registry = ReportSectionRegistry()
    registry.register(ReportSection(
        key="exec",
        title="Executive Summary",
        order=10,
        content="First version.",
    ))
    registry.register(ReportSection(
        key="exec",
        title="Executive Summary",
        order=10,
        content="Updated version.",
    ))
    sections = registry.ordered_sections()
    assert len(sections) == 1
    assert sections[0].content == "Updated version."
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage7a_report_sections.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/game_survey_workbench/services/report_sections.py
"""Section-based report assembly.

Reports are built from an ordered registry of sections.
Each section has a key (for replacement), a display title,
an order (for sorting), and markdown content.
Empty sections are skipped during assembly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ReportSection:
    key: str
    title: str
    order: int
    content: str


class ReportSectionRegistry:
    """Ordered collection of report sections, keyed for replacement."""

    def __init__(self) -> None:
        self._sections: dict[str, ReportSection] = {}

    def register(self, section: ReportSection) -> None:
        self._sections[section.key] = section

    def ordered_sections(self) -> list[ReportSection]:
        return sorted(self._sections.values(), key=lambda s: s.order)

    def get(self, key: str) -> ReportSection | None:
        return self._sections.get(key)


def assemble_report_markdown(
    *,
    title: str,
    date: str,
    registry: ReportSectionRegistry,
) -> str:
    """Assemble a complete Markdown report from registered sections."""
    lines = [f"# {title}", "", f"*Report generated {date}*", ""]

    for section in registry.ordered_sections():
        if not section.content or not section.content.strip():
            continue
        lines.append(f"## {section.title}")
        lines.append("")
        lines.append(section.content)
        lines.append("")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stage7a_report_sections.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/report_sections.py \
        tests/test_stage7a_report_sections.py
git commit -m "feat(stage7a): add report section registry and assembly"
```

---

### Task 2: Brief-Aware Report Context Builder

**Why now:** With the section registry in place, we need a builder that populates sections from existing analysis artifacts. The most impactful first section is the methodology/background section that draws from the Research Brief — this is what makes the report self-contained.

**Files:**
- Create: `src/game_survey_workbench/services/report_builder.py`
- Test: `tests/test_stage7a_report_builder.py`

**Step 1: Write the failing test**

```python
# tests/test_stage7a_report_builder.py
"""Report builder populates sections from analysis artifacts."""
import pytest
from game_survey_workbench.services.report_builder import build_report_sections
from game_survey_workbench.services.report_sections import ReportSectionRegistry


def test_builder_creates_methodology_from_brief():
    brief = {
        "background": "Mobile game player satisfaction study",
        "objectives": ["Understand churn drivers", "Evaluate monetization perception"],
        "target_audience": "Players with 30+ days tenure",
        "hypotheses": ["High spenders are more satisfied"],
    }
    dataset_meta = {
        "row_count": 500,
        "question_count": 15,
        "question_types": {"single_choice": 8, "free_text": 3, "scale": 4},
    }
    registry = build_report_sections(
        brief=brief,
        dataset_meta=dataset_meta,
        statistical_findings=[],
        coded_themes=[],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[],
    )
    methodology = registry.get("methodology")
    assert methodology is not None
    assert "500" in methodology.content  # sample size
    assert "player satisfaction" in methodology.content.lower()


def test_builder_creates_executive_summary_from_insight():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 200, "question_count": 10, "question_types": {}},
        statistical_findings=["Satisfaction: 4.2/5 mean"],
        coded_themes=[],
        insight_narrative="Players express high satisfaction but concerns about pricing.",
        evidence_section="Source: churn_framework.md",
        recommendations=[],
    )
    exec_summary = registry.get("executive_summary")
    assert exec_summary is not None
    assert "satisfaction" in exec_summary.content.lower() or \
           "pricing" in exec_summary.content.lower()


def test_builder_creates_findings_from_deterministic_results():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[
            "Satisfaction (scale): mean 4.1, top-2 box 78%",
            "Preferred mode (single_choice): Battle Royale (42%)",
        ],
        coded_themes=[
            {"theme_name": "Pricing concerns", "count": 15, "example_responses": ["too expensive"]},
        ],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[],
    )
    findings = registry.get("statistical_findings")
    assert findings is not None
    assert "4.1" in findings.content
    themes = registry.get("qualitative_themes")
    assert themes is not None
    assert "Pricing concerns" in themes.content


def test_builder_creates_recommendations_section():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[],
        coded_themes=[],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[
            "Reduce gem pack pricing by 15% to address price sensitivity",
            "Add battle pass for mid-spenders based on segment gap",
        ],
    )
    recs = registry.get("recommendations")
    assert recs is not None
    assert "gem pack" in recs.content.lower()
    assert "battle pass" in recs.content.lower()


def test_builder_includes_evidence_basis():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[],
        coded_themes=[],
        insight_narrative=None,
        evidence_section="- **Churn Framework**: retention benchmarks\n- **IAP Guide**: pricing tiers",
        recommendations=[],
    )
    evidence = registry.get("evidence_basis")
    assert evidence is not None
    assert "Churn Framework" in evidence.content


def test_builder_without_brief_skips_methodology_background():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[],
    )
    methodology = registry.get("methodology")
    assert methodology is not None
    # Should still have sample size even without brief
    assert "100" in methodology.content
    # But no research background
    assert "background" not in methodology.content.lower() or \
           methodology.content.count("background") == 0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage7a_report_builder.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/game_survey_workbench/services/report_builder.py
"""Build structured report sections from analysis artifacts.

This module bridges analysis outputs (findings, themes, insights,
recommendations) and the section-based report assembly. It creates
a ReportSectionRegistry populated from whatever artifacts are available.
"""
from __future__ import annotations

from game_survey_workbench.services.report_sections import (
    ReportSection,
    ReportSectionRegistry,
)


def build_report_sections(
    *,
    brief: dict | None,
    dataset_meta: dict,
    statistical_findings: list[str],
    coded_themes: list[dict],
    insight_narrative: str | None,
    evidence_section: str | None,
    recommendations: list[str],
) -> ReportSectionRegistry:
    """Populate a section registry from available analysis artifacts."""
    registry = ReportSectionRegistry()

    # 1. Executive Summary (from insight narrative or findings summary)
    exec_content = _build_executive_summary(
        insight_narrative=insight_narrative,
        statistical_findings=statistical_findings,
    )
    if exec_content:
        registry.register(ReportSection(
            key="executive_summary",
            title="Executive Summary",
            order=10,
            content=exec_content,
        ))

    # 2. Methodology (from brief + dataset meta)
    methodology_content = _build_methodology(
        brief=brief,
        dataset_meta=dataset_meta,
    )
    registry.register(ReportSection(
        key="methodology",
        title="Methodology",
        order=20,
        content=methodology_content,
    ))

    # 3. Statistical Findings
    if statistical_findings:
        findings_md = "\n".join(f"- {f}" for f in statistical_findings)
        registry.register(ReportSection(
            key="statistical_findings",
            title="Statistical Findings",
            order=30,
            content=findings_md,
        ))

    # 4. Qualitative Themes (from coded open-text)
    if coded_themes:
        themes_md = _build_themes_section(coded_themes)
        registry.register(ReportSection(
            key="qualitative_themes",
            title="Qualitative Themes",
            order=40,
            content=themes_md,
        ))

    # 5. Analysis Narrative (full LLM insight)
    if insight_narrative:
        registry.register(ReportSection(
            key="analysis_narrative",
            title="Analysis",
            order=50,
            content=insight_narrative,
        ))

    # 6. Recommendations
    if recommendations:
        recs_md = "\n".join(f"- {r}" for r in recommendations)
        registry.register(ReportSection(
            key="recommendations",
            title="Recommendations",
            order=60,
            content=recs_md,
        ))

    # 7. Evidence Basis
    if evidence_section:
        registry.register(ReportSection(
            key="evidence_basis",
            title="Evidence Basis",
            order=90,
            content=evidence_section,
        ))

    return registry


def _build_executive_summary(
    *,
    insight_narrative: str | None,
    statistical_findings: list[str],
) -> str:
    """Extract or build executive summary content."""
    if insight_narrative:
        # Use first paragraph of insight narrative as summary
        paragraphs = insight_narrative.strip().split("\n\n")
        return paragraphs[0] if paragraphs else ""
    if statistical_findings:
        return "Key findings from this analysis:\n\n" + "\n".join(
            f"- {f}" for f in statistical_findings[:5]
        )
    return ""


def _build_methodology(
    *,
    brief: dict | None,
    dataset_meta: dict,
) -> str:
    """Build methodology section from brief and dataset metadata."""
    lines = []

    if brief:
        bg = brief.get("background", "")
        if bg:
            lines.append(f"**Research Background:** {bg}")
            lines.append("")
        objectives = brief.get("objectives", [])
        if objectives:
            lines.append("**Research Objectives:**")
            for obj in objectives:
                lines.append(f"- {obj}")
            lines.append("")
        audience = brief.get("target_audience", "")
        if audience:
            lines.append(f"**Target Audience:** {audience}")
            lines.append("")

    row_count = dataset_meta.get("row_count", 0)
    q_count = dataset_meta.get("question_count", 0)
    q_types = dataset_meta.get("question_types", {})

    lines.append(f"**Sample:** {row_count} respondents, {q_count} questions")
    if q_types:
        type_parts = [f"{v} {k.replace('_', ' ')}" for k, v in q_types.items() if v]
        if type_parts:
            lines.append(f"**Question Types:** {', '.join(type_parts)}")

    return "\n".join(lines)


def _build_themes_section(coded_themes: list[dict]) -> str:
    """Format coded themes into a readable section."""
    lines = []
    for theme in coded_themes:
        name = theme.get("theme_name", "Unknown")
        count = theme.get("count", 0)
        examples = theme.get("example_responses", [])
        lines.append(f"**{name}** (n={count})")
        for ex in examples[:2]:
            lines.append(f'  - _"{ex}"_')
        lines.append("")
    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stage7a_report_builder.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/report_builder.py \
        tests/test_stage7a_report_builder.py
git commit -m "feat(stage7a): add brief-aware report builder with structured sections"
```

---

### Task 3: Recommendation Extraction from Insight Narrative

**Why now:** The insight synthesis prompt already asks the LLM to output "Recommended Actions" as a structured list inside the narrative. But these are currently buried in free text. This task extracts them deterministically so the report builder can create a standalone Recommendations section.

**Files:**
- Create: `src/game_survey_workbench/services/recommendation_extractor.py`
- Test: `tests/test_stage7b_recommendation_extractor.py`

**Step 1: Write the failing test**

```python
# tests/test_stage7b_recommendation_extractor.py
"""Extract structured recommendations from insight narrative."""
import pytest
from game_survey_workbench.services.recommendation_extractor import (
    extract_recommendations,
)


def test_extract_bullet_recommendations():
    narrative = """## Executive Takeaway
Players show declining satisfaction.

## Supporting Analysis
Satisfaction dropped 12% month-over-month.

## Recommended Actions
- Reduce gem pricing by 15% to address price sensitivity (evidence: 42% cite "too expensive")
- Add a battle pass tier for mid-spenders (evidence: segment gap in $5-$20 range)
- Improve tutorial flow for new players (evidence: coded theme "Confusion", n=18)

## Open Questions
- Need longitudinal data to confirm trend
"""
    recs = extract_recommendations(narrative)
    assert len(recs) == 3
    assert "gem pricing" in recs[0].lower()
    assert "battle pass" in recs[1].lower()


def test_extract_from_narrative_without_header():
    narrative = """Key findings show satisfaction is high.

Consider reducing prices because feedback indicates sensitivity.
Consider adding more game modes based on player requests."""
    recs = extract_recommendations(narrative)
    # Should handle gracefully — may return empty if no clear section
    assert isinstance(recs, list)


def test_extract_empty_narrative():
    recs = extract_recommendations("")
    assert recs == []


def test_extract_none_narrative():
    recs = extract_recommendations(None)
    assert recs == []
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage7b_recommendation_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement extraction**

```python
# src/game_survey_workbench/services/recommendation_extractor.py
"""Extract structured recommendations from LLM insight narratives.

The insight synthesis prompt asks for a '## Recommended Actions' section
with bullet points. This module extracts those bullets deterministically
so they can be displayed as a standalone report section.
"""
from __future__ import annotations

import re


def extract_recommendations(narrative: str | None) -> list[str]:
    """Extract recommendation bullets from an insight narrative.

    Looks for a section headed 'Recommended Actions' or 'Recommendations'
    and extracts the bullet points that follow.
    """
    if not narrative:
        return []

    # Find the recommendations section
    pattern = r"#+\s*Recommend(?:ed\s+Actions|ations)\s*\n(.*?)(?=\n#+\s|\Z)"
    match = re.search(pattern, narrative, re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    section_text = match.group(1).strip()
    bullets = []
    for line in section_text.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            bullets.append(line[2:].strip())
        elif line.startswith("1.") or re.match(r"^\d+\.\s", line):
            bullets.append(re.sub(r"^\d+\.\s*", "", line).strip())

    return [b for b in bullets if b]
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stage7b_recommendation_extractor.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/recommendation_extractor.py \
        tests/test_stage7b_recommendation_extractor.py
git commit -m "feat(stage7b): add deterministic recommendation extraction from insight narrative"
```

---

### Task 4: Wire Report Builder into Report Generation Route

**Why now:** The section registry and builder are ready. This task replaces the old monolithic template render with the new structured pipeline.

**Files:**
- Modify: `src/game_survey_workbench/services/reporting.py`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Test: `tests/test_stage7c_structured_report.py`

**Step 1: Write the failing test**

```python
# tests/test_stage7c_structured_report.py
"""End-to-end structured report generation."""
import pytest
from fastapi.testclient import TestClient
from game_survey_workbench.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(workspace_root=tmp_path)
    return TestClient(app, follow_redirects=False)


def _setup_full_project(client, tmp_path):
    """Create project with brief, dataset, and trigger analysis."""
    # Create project
    client.post("/projects", json={"slug": "rpt-test", "name": "Report Test"})

    # Save brief
    client.put("/projects/rpt-test/brief", json={
        "background": "Mobile game satisfaction study Q1 2026",
        "objectives": ["Measure overall satisfaction", "Identify churn risk factors"],
        "target_audience": "Players with 14+ days tenure",
        "hypotheses": ["Spenders are more satisfied than non-spenders"],
    })

    # Import dataset
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "satisfaction,feedback\n"
        "scale,free_text\n"
        "5,great game love it\n"
        "3,too many ads\n"
        "4,good but expensive\n"
        "2,boring after a week\n"
    )
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/projects/rpt-test/datasets/import",
            files={"file": ("survey.csv", f, "text/csv")},
        )
    return resp.json().get("analysis_run_id")


def test_structured_report_has_methodology(client, tmp_path):
    run_id = _setup_full_project(client, tmp_path)
    resp = client.post(
        "/projects/rpt-test/reports/generate",
        json={"analysis_run_id": run_id},
    )
    assert resp.status_code == 200
    report_path = resp.json().get("path", "")
    if report_path:
        content = (tmp_path / report_path.lstrip("/")).read_text()
    else:
        content = resp.json().get("markdown", "")
    assert "Methodology" in content or "methodology" in content.lower()


def test_structured_report_has_brief_context(client, tmp_path):
    run_id = _setup_full_project(client, tmp_path)
    resp = client.post(
        "/projects/rpt-test/reports/generate",
        json={"analysis_run_id": run_id},
    )
    report = resp.json()
    content = report.get("markdown", "")
    # Brief objectives should appear in the report
    assert "satisfaction" in content.lower() or "churn" in content.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage7c_structured_report.py -v`
Expected: FAIL — report doesn't contain "Methodology"

**Step 3: Modify reporting service to use report builder**

In `src/game_survey_workbench/services/reporting.py`, replace the existing `render_report_markdown()` or equivalent with:

```python
from game_survey_workbench.services.report_builder import build_report_sections
from game_survey_workbench.services.report_sections import assemble_report_markdown
from game_survey_workbench.services.recommendation_extractor import extract_recommendations

def generate_structured_report(
    *,
    project_name: str,
    brief: dict | None,
    dataset_meta: dict,
    statistical_findings: list[str],
    coded_themes: list[dict],
    insight_narrative: str | None,
    evidence_section: str | None,
) -> str:
    """Generate a structured Markdown report."""
    recommendations = extract_recommendations(insight_narrative)

    registry = build_report_sections(
        brief=brief,
        dataset_meta=dataset_meta,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
        insight_narrative=insight_narrative,
        evidence_section=evidence_section,
        recommendations=recommendations,
    )

    from datetime import date
    return assemble_report_markdown(
        title=f"{project_name} Research Report",
        date=date.today().isoformat(),
        registry=registry,
    )
```

Update the report route to collect brief and dataset metadata and call `generate_structured_report()`.

**Step 4: Run tests**

Run: `python -m pytest tests/test_stage7c_structured_report.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing (existing report tests may need minor assertion updates if they check for old template format)

**Step 6: Commit**

```bash
git add src/game_survey_workbench/services/reporting.py \
        src/game_survey_workbench/routes/reports.py \
        tests/test_stage7c_structured_report.py
git commit -m "feat(stage7c): wire structured report builder into generation route"
```

---

### Task 5: Report Versioning

**Why now:** Questionnaire versioning was added in Stage 6C. Reports need the same capability — a researcher who regenerates a report after refining insights should be able to compare the two versions.

**Files:**
- Modify: `src/game_survey_workbench/models/reporting.py`
- Create: `src/game_survey_workbench/services/report_versions.py`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Create: `src/game_survey_workbench/templates/reports/history.html`
- Test: `tests/test_stage7d_report_versions.py`

**Step 1: Write the failing test**

```python
# tests/test_stage7d_report_versions.py
"""Report versioning and comparison."""
import pytest
from game_survey_workbench.services.report_versions import (
    list_report_versions,
    diff_report_versions,
)


def test_list_report_versions(db_session):
    from game_survey_workbench.models.reporting import ReportRecord

    for i in range(3):
        r = ReportRecord(
            project_slug="proj-a",
            analysis_run_id=f"run-{i}",
            path=f"/reports/v{i}.md",
        )
        db_session.add(r)
    db_session.commit()

    versions = list_report_versions(db_session, "proj-a")
    assert len(versions) == 3
    # Most recent first
    assert versions[0].path == "/reports/v2.md"


def test_diff_report_versions(tmp_path):
    from game_survey_workbench.services.report_versions import diff_report_content

    report_a = "# Report\n\n## Findings\n- Satisfaction: 4.1\n"
    report_b = "# Report\n\n## Findings\n- Satisfaction: 4.3\n- New finding\n"

    diff = diff_report_content(report_a, report_b, "v1", "v2")
    assert diff.added_lines >= 1
    assert "4.3" in diff.unified_diff
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage7d_report_versions.py -v`
Expected: FAIL — module not found

**Step 3: Implement report versioning**

```python
# src/game_survey_workbench/services/report_versions.py
"""Report version history and diff utilities.

Mirrors questionnaire_versions.py pattern for consistency.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass

from sqlmodel import Session, select

from game_survey_workbench.models.reporting import ReportRecord


def list_report_versions(
    session: Session, project_slug: str
) -> list[ReportRecord]:
    """Return all report records for a project, most recent first."""
    stmt = (
        select(ReportRecord)
        .where(ReportRecord.project_slug == project_slug)
        .order_by(ReportRecord.created_at.desc())
    )
    return list(session.exec(stmt).all())


@dataclass
class ReportDiff:
    version_a: str
    version_b: str
    added_lines: int
    removed_lines: int
    unified_diff: str


def diff_report_content(
    content_a: str,
    content_b: str,
    label_a: str = "previous",
    label_b: str = "current",
) -> ReportDiff:
    """Compute a unified diff between two report contents."""
    lines_a = content_a.splitlines(keepends=True)
    lines_b = content_b.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(lines_a, lines_b, fromfile=label_a, tofile=label_b)
    )
    unified = "".join(diff_lines)
    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

    return ReportDiff(
        version_a=label_a,
        version_b=label_b,
        added_lines=added,
        removed_lines=removed,
        unified_diff=unified,
    )
```

**Step 4: Add report history route and template**

Route in `reports.py`:
```python
@router.get("/projects/{project_slug}/reports/history")
def report_history(project_slug: str, request: Request):
    versions = list_report_versions(session, project_slug)
    return templates.TemplateResponse(
        "reports/history.html",
        {"request": request, "project_slug": project_slug, "versions": versions},
    )
```

Template `reports/history.html`:
```html
{% extends "layout.html" %}
{% block content %}
<h1>Report History — {{ project_slug }}</h1>
{% if versions %}
<table>
  <thead>
    <tr><th>Run ID</th><th>Created</th><th>Path</th></tr>
  </thead>
  <tbody>
    {% for v in versions %}
    <tr>
      <td>{{ v.analysis_run_id }}</td>
      <td>{{ v.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
      <td><a href="/projects/{{ project_slug }}/reports/latest">{{ v.path }}</a></td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}
{% endblock %}
```

**Step 5: Run tests and commit**

Run: `python -m pytest --tb=short -q`
Expected: All passing

```bash
git add src/game_survey_workbench/services/report_versions.py \
        src/game_survey_workbench/models/reporting.py \
        src/game_survey_workbench/routes/reports.py \
        src/game_survey_workbench/templates/reports/history.html \
        tests/test_stage7d_report_versions.py
git commit -m "feat(stage7d): add report version history and diff comparison"
```

---

### Task 6: Dataset Metadata Extraction for Report Context

**Why now:** The report builder needs `dataset_meta` (row count, question count, question types) to generate the methodology section. This data exists in the dataset schema but isn't currently surfaced as a simple summary dict.

**Files:**
- Create: `src/game_survey_workbench/services/dataset_meta.py`
- Test: `tests/test_stage7b_dataset_meta.py`

**Step 1: Write the failing test**

```python
# tests/test_stage7b_dataset_meta.py
"""Extract dataset metadata for report context."""
import pytest
from game_survey_workbench.services.dataset_meta import extract_dataset_meta


def test_extract_meta_from_schema():
    schema = {
        "columns": {
            "satisfaction": {"type": "scale"},
            "game_mode": {"type": "single_choice"},
            "feedback": {"type": "free_text"},
            "features": {"type": "multi_select"},
            "features_2": {"type": "multi_select"},
        }
    }
    meta = extract_dataset_meta(schema=schema, row_count=500)
    assert meta["row_count"] == 500
    assert meta["question_count"] == 5
    assert meta["question_types"]["scale"] == 1
    assert meta["question_types"]["single_choice"] == 1
    assert meta["question_types"]["free_text"] == 1
    assert meta["question_types"]["multi_select"] == 2


def test_extract_meta_empty_schema():
    meta = extract_dataset_meta(schema={}, row_count=0)
    assert meta["row_count"] == 0
    assert meta["question_count"] == 0
    assert meta["question_types"] == {}
```

**Step 2: Implement**

```python
# src/game_survey_workbench/services/dataset_meta.py
"""Extract dataset metadata summaries for report context."""
from __future__ import annotations

from collections import Counter


def extract_dataset_meta(*, schema: dict, row_count: int) -> dict:
    """Summarize dataset schema into report-ready metadata."""
    columns = schema.get("columns", {})
    type_counts: dict[str, int] = Counter()
    for col_info in columns.values():
        q_type = col_info.get("type", "unknown") if isinstance(col_info, dict) else "unknown"
        type_counts[q_type] += 1

    return {
        "row_count": row_count,
        "question_count": len(columns),
        "question_types": dict(type_counts),
    }
```

**Step 3: Run tests and commit**

Run: `python -m pytest tests/test_stage7b_dataset_meta.py -v`
Expected: 2 passed

```bash
git add src/game_survey_workbench/services/dataset_meta.py \
        tests/test_stage7b_dataset_meta.py
git commit -m "feat(stage7b): add dataset metadata extraction for report methodology section"
```

---

### Task 7: Report Detail Page Enhancement

**Why now:** The browser report view (`reports/detail.html`) currently shows raw markdown in a `<pre>` tag. With structured sections now generating the report, the detail page should render the markdown as HTML sections for readability, and link to version history.

**Files:**
- Modify: `src/game_survey_workbench/templates/reports/detail.html`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Test: `tests/test_stage7e_report_detail.py`

**Step 1: Write the failing test**

```python
# tests/test_stage7e_report_detail.py
"""Report detail page shows structured content and history link."""
import pytest
from fastapi.testclient import TestClient
from game_survey_workbench.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(workspace_root=tmp_path)
    return TestClient(app)


def test_report_page_has_history_link(client, tmp_path):
    # Create project and generate a report
    client.post("/projects", json={"slug": "detail-proj", "name": "Detail"})
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Q1\nsingle_choice\nA\nB\n")
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/projects/detail-proj/datasets/import",
            files={"file": ("data.csv", f, "text/csv")},
        )
    run_id = resp.json().get("analysis_run_id")
    client.post(
        "/projects/detail-proj/reports/generate",
        json={"analysis_run_id": run_id},
    )
    resp = client.get("/projects/detail-proj/reports/latest")
    assert resp.status_code == 200
    assert b"history" in resp.content.lower() or b"History" in resp.content
```

**Step 2: Update template to include history link**

In `reports/detail.html`, add:
```html
<a href="/projects/{{ project_slug }}/reports/history">View Report History</a>
```

**Step 3: Run tests and commit**

```bash
git add src/game_survey_workbench/templates/reports/detail.html \
        src/game_survey_workbench/routes/reports.py \
        tests/test_stage7e_report_detail.py
git commit -m "feat(stage7e): enhance report detail page with history link"
```

---

### Task 8: North-Star Update and Regression Verification

**Files:**
- Modify: `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`

**Step 1: Add Stage 7 to north-star**

Add the Stage 7 section after Stage 6:

```markdown
### Stage 7: Report Intelligence and Structured Research Output

Goal:

- make the Markdown report structured, brief-aware, version-tracked, and actionable

Scope:

- section-based report assembly replacing monolithic template
- brief-aware methodology section with research context
- deterministic recommendation extraction from insight narrative
- structured findings sections (statistical, qualitative, analysis)
- report version history and diff comparison
- dataset metadata injection into report context

Important note:

- this stage strengthens the core loop endpoint without changing output format (stays Markdown)
- no new dependencies

Status:

- Stage 7A `Report Section Registry + Builder`: [pending]
- Stage 7B `Recommendation Extraction + Dataset Meta`: [pending]
- Stage 7C `Structured Report Wiring`: [pending]
- Stage 7D `Report Versioning`: [pending]
- Stage 7E `Report Detail Enhancement`: [pending]
```

**Step 2: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing, count ≥ 195 (baseline ~184 + new Stage 7 tests)

**Step 3: Commit**

```bash
git add docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md
git commit -m "docs: update north-star with Stage 7 report intelligence plan"
```

---

## Dependency Graph

```
Task 1 (section registry)
  └─→ Task 2 (report builder)
        └─→ Task 4 (wire into route) ←── Task 3 (recommendation extractor)
                                     ←── Task 6 (dataset metadata)
              └─→ Task 7 (detail page enhancement)
Task 5 (report versioning) — independent of Tasks 1-4, can parallel
Task 8 (north-star update) — after all other tasks
```

**Parallelizable groups:**
- Group A: Tasks 1 → 2 → 4 → 7 (report assembly pipeline)
- Group B: Task 3 (recommendation extraction) — can parallel with Task 2
- Group C: Task 5 (report versioning) — fully independent
- Group D: Task 6 (dataset metadata) — can parallel with Tasks 1-3

**Optimal execution order with parallelism:**
1. Tasks 1, 3, 5, 6 in parallel (all independent)
2. Task 2 after Task 1
3. Task 4 after Tasks 2, 3, 6
4. Task 7 after Task 4
5. Task 8 after all

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing report tests break when template changes | High | Medium | Old tests will need assertion updates; run full suite after Task 4 |
| Recommendation extraction regex misses LLM output variations | Medium | Low | Regex is permissive; unmatched recs stay in narrative section |
| Brief not available for older projects without Stage 3 data | Low | Low | Builder handles `brief=None` gracefully — methodology still shows sample size |
| Report diff is noisy for large reports | Low | Low | Same difflib approach proven in questionnaire versioning |

## Verification Checklist

After all tasks:

- [ ] `python -m pytest --tb=short -q` — all tests pass, count ≥ 195
- [ ] Generated report contains structured sections: Executive Summary, Methodology, Findings, Recommendations, Evidence Basis
- [ ] Report methodology section includes brief context (background, objectives, audience) when available
- [ ] Recommendations are extracted from insight narrative into standalone section
- [ ] Report history page lists all report versions for a project
- [ ] Report detail page links to version history
- [ ] Reports without brief still generate valid methodology (sample size only)
- [ ] North-star document reflects Stage 7 status
