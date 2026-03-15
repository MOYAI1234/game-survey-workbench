# 游戏问卷研究工作台

一个面向中文研究者的本地优先研究工作台，用共享知识库驱动问卷设计、问卷数据分析与 Markdown 报告生成。

- 共享知识库
- 问卷设计
- 数据分析
- Markdown 报告生成

系统以 Python 单体应用实现，使用 FastAPI 提供 HTTP 接口和本地 Web 页面，使用 SQLite 保存项目与运行记录，使用本地文件夹保存知识库、数据集和报告产物。

## 当前能力

当前 1.0 已支持：

- 健康检查接口 `/health`
- 项目创建与项目级研究简报
- 共享知识库页面 `/knowledge`
- Markdown 知识文档解析、本地入库和用途多选上传
- 问卷设计上下文拼装与草案版本保存
- 问卷数据导入、metadata 过滤、基础题型识别与 schema 导出
- 基础确定性统计能力、文本编码、洞察合成
- 问卷、编码、洞察在无知识或无匹配时的降级生成
- Markdown 报告渲染与版本化保存
- 中文化的本地首页、项目页、分析页、问卷页、报告页
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

### Quick Start

1. clone 仓库并进入目录
2. 配置 `.env`
3. 运行 `run.bat`

Windows 推荐启动方式：

```bat
copy .env.example .env
notepad .env
run.bat
```

`run.bat` 会做这些事情：

- 如果 `.env` 不存在，自动从 `.env.example` 创建模板并停止，要求先完成真实 LLM 配置
- 执行 `python -m uv sync --extra dev`
- 选择可用端口启动本地服务，优先尝试 `8000`，被占用时自动回退到 `8014-8018`
- 自动打开浏览器到实际启动地址

注意：

- 不要假设端口永远是 `8000`
- 以 `run.bat` 窗口中打印的 `Starting server on http://127.0.0.1:<端口>/` 为准

### LLM Configuration

系统当前支持两种模式：

- `openai_compatible`：用于真实验证，支持 OpenAI API 和 Ollama 的 OpenAI 兼容接口
- `fake`：仅用于开发或测试，不代表真实研究体验

推荐真实验证配置：

```env
GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT=workspace
GAME_SURVEY_WORKBENCH_LLM_PROVIDER=openai_compatible
GAME_SURVEY_WORKBENCH_LLM_MODEL=gpt-4.1
GAME_SURVEY_WORKBENCH_LLM_API_KEY=sk-your-openai-key
GAME_SURVEY_WORKBENCH_LLM_BASE_URL=https://api.openai.com/v1
```

本地 Ollama 示例：

```env
GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT=workspace
GAME_SURVEY_WORKBENCH_LLM_PROVIDER=openai_compatible
GAME_SURVEY_WORKBENCH_LLM_MODEL=qwen2.5:14b
GAME_SURVEY_WORKBENCH_LLM_API_KEY=ollama
GAME_SURVEY_WORKBENCH_LLM_BASE_URL=http://127.0.0.1:11434/v1
```

开发/测试用 fake 配置：

```env
GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT=workspace
GAME_SURVEY_WORKBENCH_LLM_PROVIDER=fake
GAME_SURVEY_WORKBENCH_LLM_MODEL=fake
GAME_SURVEY_WORKBENCH_LLM_API_KEY=fake
GAME_SURVEY_WORKBENCH_LLM_BASE_URL=http://localhost/fake
```

如果未完成 LLM 配置，浏览器中的问卷生成、文本编码、洞察生成等表单操作会回跳原页面，并提示：`LLM 未配置，请设置环境变量后重试`。

### 共享知识库

知识库是 `workspace` 级共享资产，不是项目私有文件夹。

- 统一入口：`/knowledge`
- 上传后文档会进入 `workspace/knowledge/`
- 多个项目共用同一套知识库
- 上传时可以直接勾选用途，无需手写 Markdown front matter

当前用途分类：

- `问卷设计`
- `问卷分析`
- `报告写作`

如果文档本身带 front matter，系统会继续兼容；但普通使用者直接在界面里勾选用途就可以。

### 首次使用流程

首次启动后，推荐按这个顺序完成验收：

1. 打开首页，确认服务已启动，并进入 `共享知识库`
2. 上传 1-3 篇 Markdown 知识文档，分别覆盖问卷设计、问卷分析或报告写作
3. 创建一个项目并填写研究简报
4. 生成问卷草案
5. 导入一份符合双层表头规范的问卷数据
6. 如果有开放题，执行文本编码；如果只有单选题/量表题，可以直接生成洞察
7. 生成并查看报告

如果某个流程没有匹配到知识，系统会尽量降级生成基础版本，而不是直接中断主流程。

安装依赖：

```bash
python -m uv sync --extra dev
```

运行测试：

```bash
python -m pytest --tb=short -q
```

编译检查：

```bash
python -m compileall src
```

手动启动本地服务：

```bash
python -m uv sync --extra dev
set PYTHONPATH=%CD%\src
python -m uvicorn --app-dir src game_survey_workbench.app:create_app --factory --host 127.0.0.1 --port 8000
```

启动后可访问：

- `http://127.0.0.1:<端口>/`
- `http://127.0.0.1:<端口>/health`
- `http://127.0.0.1:<端口>/knowledge`

其中 `<端口>` 以 `run.bat` 或你手动启动时指定的端口为准。

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
