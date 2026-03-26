# Business Report Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将最终研究报告改造成业务汇报风输出，保留工作台研究洞察视角不变。

**Architecture:** 仅修改报告生成层，不改导入、编码和洞察生成链路。通过重写报告 section builder，把统计发现、定性主题和洞察 narrative 融合成面向业务汇报的章节结构，并将参考来源压缩为末尾简表。

**Tech Stack:** Python, FastAPI, SQLModel, Markdown report assembly, pytest

---

### Task 1: 定义新的业务汇报章节结构

**Files:**
- Modify: `src/game_survey_workbench/services/report_builder.py`
- Test: `tests/test_report_builder.py`

**Step 1: Write the failing test**

在 `tests/test_report_builder.py` 新增测试，断言新的 section key 和中文标题存在：

- `executive_summary` -> `一页摘要`
- `business_insights` -> `核心洞察`
- `chart_callouts` -> `关键图表说明`
- `recommendations` -> `建议动作`
- `references` -> `参考来源`

并断言以下旧章节不存在：

- `methodology`
- `statistical_findings`
- `qualitative_themes`
- `evidence_basis`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_report_builder.py -q`

Expected: FAIL，因为 builder 仍然生成旧结构。

**Step 3: Write minimal implementation**

在 `src/game_survey_workbench/services/report_builder.py`：

- 更新 `SECTION_TITLES`
- 重写 `build_report_sections()`
- 让 registry 只注册新结构所需章节

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_report_builder.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_report_builder.py src/game_survey_workbench/services/report_builder.py
git commit -m "feat: switch reports to business summary sections"
```

### Task 2: 把统计发现和定性主题融入“核心洞察”

**Files:**
- Modify: `src/game_survey_workbench/services/report_builder.py`
- Test: `tests/test_report_builder.py`

**Step 1: Write the failing test**

新增测试，给定：

- `statistical_findings`
- `coded_themes`
- `insight_narrative`

断言 `business_insights` section：

- 不为空
- 内容中同时体现洞察 narrative 和主题/统计素材
- 不再出现“统计发现”或“定性主题”作为二级标题

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_report_builder.py -q`

Expected: FAIL

**Step 3: Write minimal implementation**

新增 builder helper，例如：

- `_build_business_insights(...)`
- `_summarize_theme_lines(...)`
- `_summarize_stat_findings(...)`

输出目标是“业务结论块”，而不是逐条列研究素材。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_report_builder.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_report_builder.py src/game_survey_workbench/services/report_builder.py
git commit -m "feat: fold findings and themes into business insights"
```

### Task 3: 新增“关键图表说明”章节

**Files:**
- Modify: `src/game_survey_workbench/services/report_builder.py`
- Test: `tests/test_report_builder.py`

**Step 1: Write the failing test**

新增测试，给定多条统计发现时，断言：

- `chart_callouts` section 被生成
- section 内容是压缩后的业务解释，而不是原始统计逐条照抄

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_report_builder.py -q`

Expected: FAIL

**Step 3: Write minimal implementation**

新增 helper，例如 `_build_chart_callouts(statistical_findings)`，输出 2-4 条“图表说明”。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_report_builder.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_report_builder.py src/game_survey_workbench/services/report_builder.py
git commit -m "feat: add chart callout section for business reports"
```

### Task 4: 把证据基础改成末尾简短参考来源

**Files:**
- Modify: `src/game_survey_workbench/services/report_builder.py`
- Test: `tests/test_report_builder.py`

**Step 1: Write the failing test**

新增测试，给定 `evidence_section` 和引用素材时，断言最终生成的是：

- `references` section
- 内容是简短列表
- 不再出现 `证据基础` 标题

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_report_builder.py -q`

Expected: FAIL

**Step 3: Write minimal implementation**

新增 helper，例如 `_build_references(...)`：

- 抽取数据源
- 抽取开放题编码来源
- 抽取知识库引用标题

输出短列表，避免长段证据说明。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_report_builder.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_report_builder.py src/game_survey_workbench/services/report_builder.py
git commit -m "feat: move report evidence into concise references"
```

### Task 5: 更新 Markdown 拼装与页面展示验证

**Files:**
- Modify: `src/game_survey_workbench/services/reporting.py`
- Modify: `src/game_survey_workbench/services/report_sections.py` (only if needed)
- Modify: `src/game_survey_workbench/templates/reports/report.md.j2` (only if still used in current path)
- Test: `tests/test_reporting.py`
- Test: `tests/test_report_pages.py`

**Step 1: Write the failing test**

新增测试，断言最终报告 Markdown：

- 包含 `一页摘要`
- 包含 `核心洞察`
- 包含 `关键图表说明`
- 包含 `建议动作`
- 以 `参考来源` 结尾附近收束
- 不包含 `研究方法 / 统计发现 / 定性主题 / 证据基础`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_reporting.py tests/test_report_pages.py -q`

Expected: FAIL

**Step 3: Write minimal implementation**

确保 `generate_structured_report()` 最终走到新的 registry 输出，并同步修正任何模板残留标题。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_reporting.py tests/test_report_pages.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_reporting.py tests/test_report_pages.py src/game_survey_workbench/services/reporting.py src/game_survey_workbench/services/report_sections.py src/game_survey_workbench/templates/reports/report.md.j2
git commit -m "feat: render final reports in business briefing style"
```

### Task 6: 全链路回归验证

**Files:**
- Test: `tests/test_end_to_end_smoke.py`
- Test: `tests/test_reporting.py`
- Test: `tests/test_report_builder.py`
- Test: `tests/test_report_pages.py`

**Step 1: Run focused report suite**

Run:

```bash
pytest tests/test_report_builder.py tests/test_reporting.py tests/test_report_pages.py -q
```

Expected: PASS

**Step 2: Run end-to-end smoke**

Run:

```bash
pytest tests/test_end_to_end_smoke.py -q
```

Expected: PASS

**Step 3: Run full test suite**

Run:

```bash
pytest -q
```

Expected: PASS

**Step 4: Commit final verification state**

```bash
git add docs/plans/2026-03-26-business-report-design.md docs/plans/2026-03-26-business-report-implementation.md
git commit -m "docs: add business report redesign plan"
```
