# Text Coding Progress UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在分析页“文本编码”卡片中展示实时状态文案和总进度条，让用户在文本编码执行过程中看到当前状态，而不是长时间无反馈。

**Architecture:** 保留现有同步 `code-text-all` 路由用于兼容测试和已有调用；新增一个仅供工作台页面使用的“后台启动文本编码”路由，以及一个聚合 `analysis_run_id` 下文本编码状态的只读接口。分析页卡片改为通过轻量 JS 轮询状态接口，显示总进度和状态文字。

**Tech Stack:** FastAPI, SQLModel, SQLite, threading, Jinja2 template, vanilla JavaScript, pytest

---

### Task 1: 固定设计范围

**Files:**
- Create: `docs/plans/2026-03-26-text-coding-progress-ui-plan.md`

**Step 1: 记录本次只做的内容**

- 在分析页文本编码卡片显示状态条和总进度条
- 新增后台启动路由
- 新增按分析运行聚合的状态接口
- 前端每几秒轮询一次

**Step 2: 记录本次不做的内容**

- 不做单独任务中心页面
- 不做每题展开详情 UI
- 不改变现有同步 API 的对外行为

### Task 2: 先写失败测试

**Files:**
- Modify: `tests/test_text_coding_routes.py`
- Modify: `tests/test_stage5c_action_triggers.py`
- Modify: `tests/test_stage6a_workflow_wiring.py`

**Step 1: 写后台启动路由测试**

- 触发新的文本编码启动路由
- 断言快速返回 `303`
- 断言不会阻塞等待全部编码完成

**Step 2: 写状态接口测试**

- 人工插入 `CodingJob/CodingBatch` 数据
- 调用状态接口
- 断言返回总题数、完成题数、总批次数、已完成批次数、进度百分比、状态文案

**Step 3: 写分析页卡片渲染测试**

- 访问分析页
- 断言存在文本编码状态容器、进度条占位和轮询所需属性

### Task 3: 实现后台启动与状态聚合

**Files:**
- Modify: `src/game_survey_workbench/routes/text_coding.py`
- Modify: `src/game_survey_workbench/routes/coding_jobs.py`
- Create: `src/game_survey_workbench/services/coding_progress.py`

**Step 1: 抽出可复用的文本编码执行函数**

- 将当前批量执行逻辑抽成服务函数
- 同步路由继续直接调用它
- 后台路由在线程中调用它

**Step 2: 实现后台启动防重入**

- 同一 `analysis_run_id` 已有运行中的编码任务时，不重复启动
- 后台线程结束后清理运行标记

**Step 3: 实现聚合状态接口**

- 按 `analysis_run_id` 汇总最新编码 job
- 生成总进度、状态文字和是否应继续轮询

### Task 4: 实现卡片 UI 和轮询

**Files:**
- Modify: `src/game_survey_workbench/routes/datasets.py`
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Modify: `src/game_survey_workbench/templates/layout.html`

**Step 1: 在分析页上下文中提供状态接口 URL**

**Step 2: 改造文本编码卡片**

- 保留结果展示
- 无结果时显示启动按钮
- 有进行中任务时显示状态行和总进度条

**Step 3: 增加前端轮询脚本**

- 每 3-5 秒拉取一次状态
- 更新文案、进度条和按钮状态
- 编码完成后停止轮询并刷新页面

### Task 5: 验证

**Step 1: 跑目标测试集**

Run:
```bash
C:\Users\69050\Documents\Playground\.venv\Scripts\python.exe -m pytest tests/test_text_coding_routes.py tests/test_stage5c_action_triggers.py tests/test_stage6a_workflow_wiring.py -q
```

**Step 2: 跑相关回归**

Run:
```bash
C:\Users\69050\Documents\Playground\.venv\Scripts\python.exe -m pytest tests/test_app_smoke.py tests/test_text_coding_service.py tests/test_batched_coding.py -q
```

**Step 3: 用真实数据再做一次重试**

- 重新触发文本编码
- 观察分析页卡片是否能持续显示状态
- 记录总耗时和最终状态
