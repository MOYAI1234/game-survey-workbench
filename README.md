# 游戏问卷研究工作台

一个面向中文研究者的本地优先研究工作台，用共享知识库驱动问卷设计、数据分析、文本编码、洞察整理与报告生成。

这份 README 按“交付给使用者”的视角来写。默认你是第一次接手这个项目，只想知道：

- 怎么启动
- 每个模块是干什么的
- 正常应该按什么顺序使用
- 模型怎么改
- 产物会保存到哪里

## 1. 这套工具能做什么

当前版本已经打通了完整的研究链路：

1. 共享知识库管理
2. 项目创建与研究波次管理
3. 问卷草稿生成与迭代
4. 问卷数据导入与基础统计
5. 开放题文本编码
6. 洞察合成
7. 业务汇报风研究报告生成

它是一个本地优先工具：

- 前端是本地 Web 页面
- 数据库存储是本地 SQLite
- 知识文档、数据集、报告文件都保存在本地 `workspace/`
- 没有登录、多用户协作和云端后台任务系统

## 2. 适合谁使用

适合这几类场景：

- 游戏问卷调研
- 玩家反馈研究
- 版本复盘
- 结合个人知识库的问卷设计和报告输出

不适合这几类场景：

- 企业级多用户协同
- 大规模在线问卷平台替代
- 完整 BI 平台替代

## 3. 快速开始

### 3.1 启动要求

- Windows
- Python 3.12
- 能访问你配置的 LLM 接口

### 3.2 推荐启动方式

```bat
copy .env.example .env
notepad .env
run.bat
```

`run.bat` 会自动：

- 检查 `.env`
- 执行 `python -m uv sync --extra dev`
- 自动选择可用端口启动服务
- 自动打开浏览器

注意：

- 不要假设端口永远是 `8000`
- 以终端里打印的 `Starting server on http://127.0.0.1:<端口>/` 为准

### 3.3 手动启动

```bash
python -m uv sync --extra dev
set PYTHONPATH=%CD%\src
python -m uvicorn --app-dir src game_survey_workbench.app:create_app --factory --host 127.0.0.1 --port 8000
```

启动后常用入口：

- 首页：`http://127.0.0.1:<端口>/`
- 健康检查：`http://127.0.0.1:<端口>/health`
- 共享知识库：`http://127.0.0.1:<端口>/knowledge`

## 4. 正常使用顺序

第一次使用，建议按这个顺序走：

1. 配置 `.env`
2. 启动服务
3. 进入共享知识库，上传 1-3 篇资料
4. 新建项目
5. 在项目概览里填写研究简报、确认当前轮次
6. 进入问卷设计页，生成草稿并按需要改稿
7. 进入数据分析页，上传问卷数据
8. 如果有开放题，执行文本编码
9. 生成洞察
10. 生成报告

一句话理解：

`知识库 -> 项目 -> 问卷 -> 数据 -> 编码 -> 洞察 -> 报告`

## 5. 模块说明

下面这一节是交付时最重要的部分。

### 5.1 首页

入口：

- `/`

作用：

- 查看所有项目
- 创建新项目
- 快速进入知识库

你会在这里看到：

- 项目列表
- 项目当前进度概览
- 知识库摘要入口

### 5.2 项目概览

入口：

- `/projects/{project_slug}`

作用：

- 管理项目级研究简报
- 选择共享知识文档
- 管理研究波次

这里是项目的“总控台”。一般在这里完成：

- 录入项目背景
- 关联当前项目要用的知识文档
- 新建或切换当前研究波次

### 5.3 共享知识库

入口：

- `/knowledge`

作用：

- 上传知识文档
- 查看索引状态
- 按用途分类筛选

支持格式：

- `.md`
- `.epub`
- `.pdf`
- `.docx`
- `.pptx`

用途分类：

- `问卷设计`
- `问卷分析`
- `报告写作`

说明：

- 知识库是 `workspace` 级共享资产，不是某个项目私有
- 多个项目会共用这里的知识文档
- 文档上传后会落到 `workspace/knowledge/`

### 5.4 问卷设计

入口：

- `/projects/{project_slug}/questionnaires/latest`

作用：

- 生成第一版问卷草稿
- 根据反馈继续改稿
- 查看问卷历史版本
- 下载 Markdown / 纯文本

输入：

- 研究目标
- 当前项目的研究简报
- 已挂载的共享知识文档

输出：

- 一份问卷 Markdown 草稿
- 可继续迭代的版本记录

什么时候用：

- 你还没有问卷
- 或者现有问卷需要结合知识库重新整理

### 5.5 数据分析

入口：

- `/projects/{project_slug}/analysis/latest`

作用：

- 上传数据
- 生成确定性统计结果
- 执行文本编码
- 生成洞察
- 从这里继续生成报告

这是整套工具里最核心的页面。

#### 5.5.1 数据导入

输入：

- 双层表头的 CSV / Excel 文件

支持格式：

- `.csv`
- `.xlsx`
- `.xls`

导入后系统会做：

- 表头校验
- 题型识别
- metadata 过滤
- 基础统计准备

#### 5.5.2 文本编码

作用：

- 只处理 `free_text` 类型题目
- 用 LLM 把开放题回答归纳成主题

输出：

- 每道开放题的主题列表
- 每个主题的回答数量

说明：

- 当前默认是串行执行
- 这样更稳，不容易因为代理抖动导致批次失败

#### 5.5.3 洞察合成

作用：

- 把统计发现、开放题主题、知识依据整合成一份洞察草稿

输入：

- 研究目标
- 统计发现
- 文本编码结果
- 知识库命中内容

输出：

- 业务可读的洞察 narrative

### 5.6 报告生成

入口：

- `/projects/{project_slug}/reports/latest`

作用：

- 基于分析结果生成最终报告
- 查看报告历史
- 下载 Markdown / 纯文本

当前报告风格：

- 业务汇报风
- 不是研究过程堆砌

默认结构：

1. 一页摘要
2. 核心洞察
3. 关键图表说明
4. 建议动作
5. 参考来源

## 6. 数据上传规范

数据文件必须使用双层表头：

- 第 1 行：题目文案或列名
- 第 2 行：类型标记
- 第 3 行开始：答卷数据

当前允许的类型标记：

- `metadata`
- `single_choice`
- `multi_select`
- `free_text`
- `scale`

其中：

- `metadata` 不进入分析题目
- 其他类型会进入分析链路

如果缺少第二层表头、类型为空、或类型不支持，接口会直接返回 `400 Bad Request`。

标准模板：

- `docs/templates/survey_import_template.csv`

## 7. 模型配置说明

这部分是交付时最需要讲清楚的。

### 7.1 配置文件位置

- 模板文件：`.env.example`
- 实际使用文件：`.env`

### 7.2 主模型配置

这组变量决定大部分 LLM 功能使用哪个模型：

```env
GAME_SURVEY_WORKBENCH_LLM_PROVIDER=openai_compatible
GAME_SURVEY_WORKBENCH_LLM_MODEL=deepseek-ai/DeepSeek-V4-Pro
GAME_SURVEY_WORKBENCH_LLM_API_KEY=sk-your-provider-key
GAME_SURVEY_WORKBENCH_LLM_BASE_URL=https://api.siliconflow.cn/v1
```

它影响的模块包括：

- 问卷设计
- 洞察生成
- 报告生成相关 LLM 输出

常见可替换场景：

- 如果你换 OpenAI：改 `MODEL / API_KEY / BASE_URL`
- 如果你换 Ollama：改 `MODEL / API_KEY / BASE_URL`
- 如果只是 UI 冒烟测试：可以切 `fake`

### 7.3 文本编码专属模型配置

文本编码可以单独指定模型：

```env
GAME_SURVEY_WORKBENCH_TEXT_CODING_MODEL=Qwen/Qwen3.5-35B-A3B
```

说明：

- 不填时，文本编码默认沿用 `GAME_SURVEY_WORKBENCH_LLM_MODEL`
- 填了以后，只影响“文本编码”
- 不影响问卷设计、洞察生成、报告生成

适用场景：

- 想给开放题编码单独换一个更便宜或更快的模型

### 7.4 文本编码性能相关参数

这几个变量只影响文本编码：

```env
GAME_SURVEY_WORKBENCH_TEXT_CODING_TIMEOUT_SECONDS=90
GAME_SURVEY_WORKBENCH_TEXT_CODING_REQUEST_MODE=chat_completions
GAME_SURVEY_WORKBENCH_TEXT_CODING_MAX_WORKERS=1
```

含义：

- `TEXT_CODING_TIMEOUT_SECONDS`
  - 单次文本编码请求的超时时间
  - 代理链路不稳定时可以适当调大

- `TEXT_CODING_REQUEST_MODE`
  - 当前建议保持 `chat_completions`
  - 这是当前文本编码链路更稳定的模式

- `TEXT_CODING_MAX_WORKERS`
  - 文本编码并发数
  - 当前默认推荐保持 `1`
  - 如果盲目提高并发，可能更容易放大代理不稳定问题

### 7.5 向量检索 / Embedding 配置

知识库检索还会用到 embedding：

```env
GAME_SURVEY_WORKBENCH_EMBEDDING_API_KEY=
GAME_SURVEY_WORKBENCH_EMBEDDING_BASE_URL=https://api.openai.com/v1
GAME_SURVEY_WORKBENCH_EMBEDDING_MODEL=text-embedding-3-small
GAME_SURVEY_WORKBENCH_EMBEDDING_DIMENSIONS=
GAME_SURVEY_WORKBENCH_RELEVANCE_THRESHOLD=1.2
```

这些变量的作用：

- `EMBEDDING_MODEL`
  - 控制知识库向量化模型

- `EMBEDDING_BASE_URL / API_KEY`
  - 控制 embedding 服务接到哪里

- `EMBEDDING_DIMENSIONS`
  - 某些模型需要手动指定维度时再填

- `RELEVANCE_THRESHOLD`
  - 控制知识库检索阈值
  - 一般不建议随便改

### 7.6 推荐的交付说明

如果你要把项目交给朋友，最简单的口径可以直接说：

1. 改主模型：改 `GAME_SURVEY_WORKBENCH_LLM_MODEL`
2. 只改文本编码模型：改 `GAME_SURVEY_WORKBENCH_TEXT_CODING_MODEL`
3. 代理地址变了：改 `GAME_SURVEY_WORKBENCH_LLM_BASE_URL`
4. API Key 变了：改 `GAME_SURVEY_WORKBENCH_LLM_API_KEY`
5. 知识库 embedding 服务变了：改 `GAME_SURVEY_WORKBENCH_EMBEDDING_*`

## 8. 默认目录结构

仓库结构：

```text
docs/plans/                     设计文档与实施计划
scripts/                        辅助脚本
src/game_survey_workbench/      应用源码
tests/                          测试
workspace/                      默认本地工作区
```

运行后的本地工作区大致如下：

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

你交付给朋友时，最需要告诉他的几件事：

- 知识文档在 `workspace/knowledge/`
- 项目数据和产物在 `workspace/projects/<project-slug>/`
- 向量库和检索产物在 `workspace/artifacts/`

## 9. 常用命令

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

生成示例工作区：

```bash
python -m uv run python scripts/seed_demo_workspace.py
```

本地 HTTP 验证：

```bash
python -m uv run --with uvicorn --with httpx python scripts/verify_local_http.py
```

## 10. 常见问题

### 10.1 页面提示 “LLM 未配置，请设置环境变量后重试”

说明 `.env` 里的主模型配置不完整。优先检查：

- `GAME_SURVEY_WORKBENCH_LLM_PROVIDER`
- `GAME_SURVEY_WORKBENCH_LLM_MODEL`
- `GAME_SURVEY_WORKBENCH_LLM_API_KEY`
- `GAME_SURVEY_WORKBENCH_LLM_BASE_URL`

### 10.2 上传数据时报 400

优先检查：

- 是否双层表头
- 第 2 行题型是否写对
- 是否存在不支持的题型

### 10.3 文本编码很慢

先不要急着加并发，建议优先检查：

- 代理是否稳定
- 当前模型是否适合长文本结构化输出
- `TEXT_CODING_TIMEOUT_SECONDS` 是否太短

默认推荐：

- `GAME_SURVEY_WORKBENCH_TEXT_CODING_MAX_WORKERS=1`

### 10.4 报告导出后还能再编辑吗

可以。报告默认保存为 Markdown，适合继续人工编辑、复制到飞书/Notion/Word 再整理。

## 11. 交付建议

如果你把项目交给朋友，建议至少同时交付这几样东西：

1. 仓库代码
2. `.env.example`
3. 一份可运行的 `.env` 示例
4. 一份示例知识文档
5. 一份标准格式的问卷数据模板
6. 这份 README

如果朋友不是开发者，建议你再额外告诉他一句：

> 正常只需要改 `.env`，然后运行 `run.bat`；日常使用主要在浏览器里完成，不需要改代码。
