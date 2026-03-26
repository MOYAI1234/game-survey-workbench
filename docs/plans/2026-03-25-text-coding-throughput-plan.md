# Text Coding Throughput Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不重构两阶段编码的前提下，把开放题文本编码的真实总耗时明显压缩下来，优先通过题间并行和减少批次数实现 3-4 分钟级别的优化目标。

**Architecture:** 保持现有单题编码和批处理结构不变，只改三处低风险瓶颈：`code-text-all` 由串行改为题间并行、批大小从 `80` 提到 `120`、是否进入批处理改为按去重后的回答数判断。同时补上并发下的 SQLite 连接参数，避免多线程编码时偶发锁库或线程绑定错误。

**Tech Stack:** FastAPI, SQLModel, SQLite, concurrent.futures.ThreadPoolExecutor, pytest

---

### Task 1: 固定实现边界并记录设计

**Files:**
- Create: `docs/plans/2026-03-25-text-coding-throughput-plan.md`

**Step 1: 记录本次只做的范围**

- 题间并行，`max_workers=3`
- `DEFAULT_BATCH_SIZE = 120`
- 去重后再决定是否分批
- 汇总所有题的执行状态后再记录工作流事件
- SQLite 增加并发友好的连接参数

**Step 2: 明确本次不做的范围**

- 不做单题内部 batch 并行
- 不做两阶段 codebook merge
- 不改变对外路由返回结构

### Task 2: 先写失败测试覆盖目标行为

**Files:**
- Modify: `tests/test_text_coding_routes.py`
- Modify: `tests/test_stage6a_workflow_wiring.py`
- Modify: `tests/test_text_coding_service.py`

**Step 1: 写题间并行测试**

- 给 `code-text-all` 准备两个 `free_text` 问题
- monkeypatch 编码函数，让每题进入时增加活动计数并短暂休眠
- 断言最大并发数至少为 `2`

**Step 2: 写工作流汇总状态测试**

- monkeypatch 题级编码函数，让其中一题返回 `partial`
- 调用 `code-text-all`
- 断言分析运行的工作流事件记录为失败而不是完成

**Step 3: 写去重阈值测试**

- 构造 121 条原始回答，但去重后只剩 2 条
- 断言文本编码走单次调用路径，而不是创建批处理 job

**Step 4: 跑测试确认先失败**

- 只运行新增/修改过的测试
- 确认失败原因对应缺失的并行与汇总逻辑，而不是测试写错

### Task 3: 实现题间并行与状态汇总

**Files:**
- Modify: `src/game_survey_workbench/routes/text_coding.py`
- Modify: `src/game_survey_workbench/services/text_coding.py`

**Step 1: 增加题级编码包装函数**

- 新增内部 helper，返回 `(CodingResult, execution_status)`
- 单批路径返回 `done`
- 分批路径返回 job 的最终状态 `done/partial/failed`

**Step 2: 将 `code_text_all` 改为题间并行**

- 先收集所有 `free_text` 题和对应 responses
- 用 `ThreadPoolExecutor(max_workers=3)` 并行调用题级编码
- 收集每题返回的状态和异常

**Step 3: 汇总工作流事件**

- 没有 `free_text` 题时维持当前行为
- 所有题都 `done` 时记录 `coding_complete`
- 任一题 `partial/failed` 或抛异常时记录 `coding_failed`

### Task 4: 实现批大小与去重阈值优化

**Files:**
- Modify: `src/game_survey_workbench/services/batched_coding.py`
- Modify: `src/game_survey_workbench/services/text_coding.py`

**Step 1: 将批大小改为 `120`**

- 更新默认常量
- 让相关测试断言新的批次数

**Step 2: 按去重后的回答数判定是否分批**

- 在进入分批逻辑前先复用 `deduplicate_responses`
- 去重后小于等于 `120` 时走单批路径

### Task 5: 为 SQLite 增加并发安全配置

**Files:**
- Modify: `src/game_survey_workbench/db.py`

**Step 1: 调整 engine 创建参数**

- 为 SQLite 连接增加 `check_same_thread=False`
- 增加合适的超时配置

**Step 2: 配置连接级 PRAGMA**

- 设置 `journal_mode=WAL`
- 设置 `busy_timeout`

### Task 6: 验证与收尾

**Files:**
- Modify: `tests/test_batched_coding.py`（如需要同步批次数断言）

**Step 1: 跑目标测试集**

Run:
```bash
python -m pytest tests/test_text_coding_routes.py tests/test_stage6a_workflow_wiring.py tests/test_text_coding_service.py tests/test_batched_coding.py -q
```

**Step 2: 跑一组更宽的回归测试**

Run:
```bash
python -m pytest tests/test_upload_preview.py tests/test_analysis_context.py tests/test_dataset_import.py tests/test_validation_ready_llm_fallback.py -q
```

**Step 3: 如有条件，做一次真实链路验证**

- 使用现有真实数据集重新触发 `code-text-all`
- 观察总耗时、批次数和是否仍有异常重试卡顿
