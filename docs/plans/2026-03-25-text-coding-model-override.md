# Text Coding Model Override Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让文本编码阶段单独使用更快的小模型，而不影响问卷设计、洞察生成等其他 LLM 环节。

**Architecture:** 在现有通用 LLM 配置基础上增加一个“文本编码模型覆盖”配置项，默认回退到通用模型。仅 `text_coding` 路由改用新的专属 builder，其他调用方保持不变。

**Tech Stack:** Python 3.12, FastAPI, dataclasses, pytest

---

### Task 1: 增加文本编码模型配置

**Files:**
- Modify: `src/game_survey_workbench/config.py`
- Modify: `src/game_survey_workbench/llm/client.py`
- Test: `tests/test_config.py`
- Test: `tests/test_llm_client.py`

**Step 1: Write the failing test**

新增测试，验证 `get_settings()` 能读取 `GAME_SURVEY_WORKBENCH_TEXT_CODING_MODEL`，且构建文本编码 client 时优先使用该模型。

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py tests/test_llm_client.py -q`

**Step 3: Write minimal implementation**

为 `Settings` 添加字段，并提供文本编码专用 client builder。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py tests/test_llm_client.py -q`

### Task 2: 仅文本编码路由切换到专属模型

**Files:**
- Modify: `src/game_survey_workbench/routes/text_coding.py`
- Test: `tests/test_text_coding_routes.py`

**Step 1: Write the failing test**

新增路由测试，验证文本编码请求实际使用的是 `GAME_SURVEY_WORKBENCH_TEXT_CODING_MODEL`，而不是通用模型。

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_text_coding_routes.py -q`

**Step 3: Write minimal implementation**

仅替换文本编码路由中的 client 构建入口。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_text_coding_routes.py -q`

### Task 3: 文档与本地运行配置

**Files:**
- Modify: `.env.example`
- Modify: `.env` (local only)

**Step 1: Document the override**

在示例环境变量中增加文本编码模型说明。

**Step 2: Apply local override**

将本地 `.env` 中的文本编码模型设置为 `Qwen/Qwen3.5-35B-A3B`。

**Step 3: Verify end-to-end**

Run: `pytest tests/test_config.py tests/test_llm_client.py tests/test_text_coding_routes.py tests/test_text_coding_service.py -q`
