# 游戏问卷研究工作台

一个面向游戏行业研究者的本地优先研究工作台，用知识库驱动问卷设计、问卷数据分析与 Markdown 报告生成。

- 问卷设计
- 数据分析
- Markdown 报告生成

系统以 Python 单体应用实现，使用 FastAPI 提供 HTTP 接口和本地 Web 页面，使用 SQLite 保存项目与运行记录，使用本地文件夹保存知识库、数据集和报告产物。

## 当前能力

当前 MVP 已支持：

- 健康检查接口 `/health`
- 项目创建与 Knowledge Pack 配置
- Markdown 知识文档解析与本地入库
- 问卷设计上下文拼装与草案版本保存
- 问卷数据导入、metadata 过滤、基础题型识别与 schema 导出
- 基础确定性统计能力
- 基于 LLM 接口抽象的洞察上下文拼装
- Markdown 报告渲染与版本化保存
- 本地首页与三大工作入口页面
- 端到端 smoke test

## 技术栈

- Python 3.12
- FastAPI
- Jinja2
- SQLModel
- pandas
- pytest
- uv

## 快速开始

安装依赖：

```bash
python -m uv sync --extra dev
```

运行测试：

```bash
python -m uv run pytest -v
```

编译检查：

```bash
python -m uv run python -m compileall src
```

启动本地服务：

```bash
python -m uv run --with uvicorn uvicorn game_survey_workbench.app:create_app --factory --reload
```

启动后可访问：

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`

## 初始化示例工作区

生成一个带测试示例数据的本地工作区：

```bash
python -m uv run python scripts/seed_demo_workspace.py
```

如果需要把工作区写到自定义目录，可以先设置环境变量：

```bash
$env:GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT="D:\\your-workspace"
python -m uv run python scripts/seed_demo_workspace.py
```

## 本地 HTTP 验证

项目内置了一个真实走 HTTP 的验证脚本，会自动启动应用、访问首页与接口，并完成一轮“建项目 → 生成问卷草案 → 导入数据 → 生成报告”的链路检查：

```bash
python -m uv run --with uvicorn --with httpx python scripts/verify_local_http.py
```

## 数据上传规范

数据文件必须使用双层表头：

- 第 1 行：题目文案或列名
- 第 2 行：类型标记
- 第 3 行开始：答卷数据

当前只允许这些类型标记：

- `metadata`
- `single_choice`
- `multi_select`
- `free_text`
- `scale`

其中：

- `metadata` 列不会进入 `question_columns`
- 其他类型会直接作为归一化 schema 的题型来源

如果缺少第二层表头、类型为空、或出现不支持的类型值，接口会直接返回 `400 Bad Request`，不会回退到启发式猜测。

标准模板可参考：

- `docs/templates/survey_import_template.csv`

## 数据上传与题型识别

数据导入接口使用 multipart 文件上传：

```bash
curl -X POST "http://127.0.0.1:8000/projects/demo/datasets/import" \
  -F "file=@workspace/projects/demo/data/raw/dataset.csv"
```

当前支持上传的文件格式：

- `.csv`
- `.xlsx`
- `.xls`

当前归一化 schema 会显式过滤 metadata 列，例如 `标记`、`时间戳记`，并识别这些题型：

- `single_choice`
- `multi_select`
- `free_text`
- `scale`

## 目录结构

```text
docs/plans/                     设计文档与实施计划
scripts/                        辅助脚本
src/game_survey_workbench/      应用源码
tests/                          测试与测试夹具
workspace/                      默认本地工作区
```

运行后生成的默认工作区结构大致如下：

```text
workspace/
  knowledge/
  projects/
    <project-slug>/
      questionnaire/
      data/
      analysis/
      reports/
      assets/
  artifacts/
```

## 说明

- 这是一个本地优先工具，当前不包含登录、多用户协作和后台任务系统。
- 知识库原始输入以 Markdown 为主。
- 报告输出为 Markdown，便于继续人工编辑和汇报复用。
