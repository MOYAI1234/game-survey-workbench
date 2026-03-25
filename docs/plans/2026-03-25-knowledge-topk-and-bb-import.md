# Knowledge Top-K And BB Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将项目知识检索默认上限统一调整为至多 20 段，并修复 BB 双表头数据在导入后进入分析页时的报错。

**Architecture:** 复用现有 `retrieve_project_knowledge` 分层检索入口，在共享层统一提升默认 `top_k`，避免各业务服务各改一套。数据导入问题按“真实文件复现 -> 写失败测试 -> 最小修复”的方式处理，优先修复分析页读取链路中的根因。

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pandas, pytest

---

### Task 1: 提升项目知识默认上限到 20

**Files:**
- Modify: `src/game_survey_workbench/retrieval/store.py`
- Modify: `src/game_survey_workbench/services/knowledge_ingest.py`
- Modify: `src/game_survey_workbench/services/insights.py`
- Test: `tests/test_stage20_layered_retrieval.py`
- Test: `tests/test_retrieval_service.py`

**Step 1: Write the failing test**

新增测试，验证未显式传 `top_k` 时，方法论池/项目知识默认返回不再被限制为 3 或 10，而是至多 20。

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_stage20_layered_retrieval.py tests/test_retrieval_service.py -q`

**Step 3: Write minimal implementation**

仅调整共享默认值，不改变显式传参行为。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_stage20_layered_retrieval.py tests/test_retrieval_service.py -q`

**Step 5: Commit**

```bash
git add src/game_survey_workbench/retrieval/store.py src/game_survey_workbench/services/knowledge_ingest.py src/game_survey_workbench/services/insights.py tests/test_stage20_layered_retrieval.py tests/test_retrieval_service.py
git commit -m "feat: raise project knowledge retrieval cap to 20"
```

### Task 2: 复现并修复 BB 双表头导入后的分析页报错

**Files:**
- Modify: `src/game_survey_workbench/services/analysis_context.py`
- Modify: `src/game_survey_workbench/services/dataset_import.py`
- Modify: `src/game_survey_workbench/routes/datasets.py`
- Test: `tests/test_app_smoke.py`
- Test: `tests/test_real_sample_understanding.py`
- Test: `tests/test_analysis_context.py`

**Step 1: Write the failing test**

用 `bb_stress_sample.csv` 或真实 BB 文件路径复现“导入成功但分析页 500”的最小用例。

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_smoke.py tests/test_analysis_context.py tests/test_real_sample_understanding.py -q`

**Step 3: Write minimal implementation**

只修复根因，不顺手改 UI 流程。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_smoke.py tests/test_analysis_context.py tests/test_real_sample_understanding.py -q`

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/analysis_context.py src/game_survey_workbench/services/dataset_import.py src/game_survey_workbench/routes/datasets.py tests/test_app_smoke.py tests/test_analysis_context.py tests/test_real_sample_understanding.py
git commit -m "fix: handle bb dataset analysis flow"
```

### Task 3: 运行整体验证

**Files:**
- Test: `tests/test_upload_preview.py`
- Test: `tests/test_dataset_import.py`
- Test: `tests/test_stage20_layered_retrieval.py`
- Test: `tests/test_retrieval_service.py`
- Test: `tests/test_app_smoke.py`

**Step 1: Run focused regression suite**

Run: `pytest tests/test_upload_preview.py tests/test_dataset_import.py tests/test_stage20_layered_retrieval.py tests/test_retrieval_service.py tests/test_app_smoke.py -q`

**Step 2: Verify real workspace compatibility**

Run a small script against `workspace/app.db` and the current server workflow to confirm no migration gaps remain.

**Step 3: Report restart requirement**

说明数据库修复是否已即时生效，以及服务进程是否需要重启才能吃到 Python 代码改动。
