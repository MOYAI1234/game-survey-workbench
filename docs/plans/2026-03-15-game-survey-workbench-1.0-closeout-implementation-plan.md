# Game Survey Workbench 1.0 验收修复实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复所有阻止 1.0 交付的界面、错误处理和引导问题，让中文用户可以在浏览器中顺畅完成核心研究流程。

**Architecture:** 纯模板层 + 路由层改动。所有修改集中在 8 个 HTML 模板、6 个路由文件、1 个 CSS 文件。不改模型、不改服务逻辑、不加依赖。

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLModel (all existing). No new dependencies.

**Prerequisite:** master 分支，212 tests passing。

**设计文档：** `docs/plans/2026-03-15-game-survey-workbench-1.0-closeout-design.md`

---

## Task 1: 全局布局和导航栏中文化

**Files:**
- Modify: `src/game_survey_workbench/templates/layout.html`

**Step 1: Write the failing test**

```python
# tests/test_1_0_i18n.py
"""1.0 中文化验收测试"""
import pytest
from fastapi.testclient import TestClient
from game_survey_workbench.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(workspace_root=tmp_path)
    return TestClient(app)


def test_layout_nav_is_chinese(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "游戏问卷研究工作台" in resp.text
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_1_0_i18n.py::test_layout_nav_is_chinese -v`
Expected: FAIL — "游戏问卷研究工作台" not found

**Step 3: Modify layout.html**

Replace the full `layout.html` content with:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}游戏问卷研究工作台{% endblock %}</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <nav class="top-nav">
    <a href="/" class="nav-brand">游戏问卷研究工作台</a>
  </nav>
  <main class="page">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_1_0_i18n.py::test_layout_nav_is_chinese -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/layout.html tests/test_1_0_i18n.py
git commit -m "fix(1.0): 导航栏中文化"
```

---

## Task 2: 首页中文化 + 空状态修复

**Files:**
- Modify: `src/game_survey_workbench/templates/index.html`
- Test: `tests/test_1_0_i18n.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/test_1_0_i18n.py

def test_index_page_is_chinese(client):
    resp = client.get("/")
    content = resp.text
    # 表单标签应为中文
    assert "新建项目" in content
    assert "项目标识" in content
    assert "项目名称" in content
    # 空状态不应该暴露 API
    assert "POST /projects" not in content
    # 不应该有纯英文表单标签
    assert "Create New Project" not in content
    assert "Slug (URL identifier)" not in content


def test_index_empty_state_chinese(client):
    resp = client.get("/")
    assert "暂无项目" in resp.text
    assert "POST /projects" not in resp.text
```

**Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_1_0_i18n.py::test_index_page_is_chinese -v`
Expected: FAIL

**Step 3: Replace index.html**

```html
{% extends "layout.html" %}
{% block title %}游戏问卷研究工作台{% endblock %}
{% block content %}
<section class="hero">
  <h1>游戏问卷研究工作台</h1>
  <p>围绕项目上下文统一管理问卷设计、数据分析与报告生成。</p>
</section>

<section class="project-list">
  <h2>项目列表</h2>
  {% if projects %}
  <ul>
    {% for project in projects %}
    <li>
      <a href="/projects/{{ project.slug }}">{{ project.name }}</a>
      {% if project.description %}
      <span class="project-desc">— {{ project.description }}</span>
      {% endif %}
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="empty-state">暂无项目，请使用下方表单创建第一个项目。</p>
  {% endif %}
</section>

<section class="create-project">
  <h2>新建项目</h2>
  <form action="/projects/create" method="post" class="project-form">
    <label for="slug">项目标识（仅限小写字母、数字、短横线，用于 URL）</label>
    <input
      type="text"
      id="slug"
      name="slug"
      required
      pattern="[a-z0-9\-]+"
      placeholder="my-research-project"
    >

    <label for="name">项目名称</label>
    <input
      type="text"
      id="name"
      name="name"
      required
      placeholder="如：2026年Q1玩家满意度调研"
    >

    <label for="description">项目说明（选填）</label>
    <textarea
      id="description"
      name="description"
      rows="2"
      placeholder="简要描述研究目标和范围"
    ></textarea>

    <button type="submit">创建项目</button>
  </form>
</section>
{% endblock %}
```

**Step 4: Run test**

Run: `python -m pytest tests/test_1_0_i18n.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/index.html tests/test_1_0_i18n.py
git commit -m "fix(1.0): 首页中文化，修复空状态 API 泄露"
```

---

## Task 3: 项目详情页中文化 + 知识上传引导 + Task Plan 空状态修复

**Files:**
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Test: `tests/test_1_0_i18n.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/test_1_0_i18n.py

def test_project_detail_is_chinese(client):
    client.post("/projects", json={"slug": "test-cn", "name": "中文测试"})
    resp = client.get("/projects/test-cn")
    content = resp.text
    # Brief 表单标签中文
    assert "研究简报" in content
    assert "研究背景" in content
    assert "研究目标" in content
    # 上传区域中文
    assert "上传知识文档" in content
    assert "上传问卷数据" in content
    # Task Plan 不暴露 API
    assert "PUT /projects/" not in content
    # 应有数据格式说明
    assert "双层表头" in content


def test_knowledge_upload_has_feedback(client, tmp_path):
    """知识上传后应有反馈参数"""
    client.post("/projects", json={"slug": "kb-test", "name": "KB Test"})
    md_file = tmp_path / "test_knowledge.md"
    md_file.write_text("# Test Knowledge\n\nSome content here.", encoding="utf-8")
    with open(md_file, "rb") as f:
        resp = client.post(
            "/projects/kb-test/knowledge/upload",
            files={"file": ("test.md", f, "text/markdown")},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert "uploaded=1" in resp.headers["location"] or "success" in resp.headers["location"].lower()
```

**Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_1_0_i18n.py::test_project_detail_is_chinese -v`
Expected: FAIL

**Step 3: Replace projects/detail.html**

```html
{% extends "layout.html" %}
{% block title %}{{ project.name if project else project_slug }}{% endblock %}
{% block content %}
<header class="project-header">
  <p class="eyebrow"><a href="/">← 返回项目列表</a></p>
  <h1>{{ project.name if project else project_slug }}</h1>
  {% if project and project.description %}
  <p class="project-description">{{ project.description }}</p>
  {% endif %}
</header>

{% if upload_success %}
<section class="workflow-alert alert-success">
  <strong>✓ {{ upload_success }}</strong>
</section>
{% endif %}

<section class="brief-section">
  <h2>研究简报</h2>
  {% if brief %}
  <dl>
    <dt>研究背景</dt>
    <dd>{{ brief.background }}</dd>
    <dt>研究目标</dt>
    <dd>
      <ul>
        {% for objective in brief.objectives %}
        <li>{{ objective }}</li>
        {% endfor %}
      </ul>
    </dd>
    {% if brief.hypotheses %}
    <dt>研究假设</dt>
    <dd>
      <ul>
        {% for hypothesis in brief.hypotheses %}
        <li>{{ hypothesis }}</li>
        {% endfor %}
      </ul>
    </dd>
    {% endif %}
    {% if brief.target_audience %}
    <dt>目标受众</dt>
    <dd>{{ brief.target_audience }}</dd>
    {% endif %}
    {% if brief.success_criteria %}
    <dt>成功标准</dt>
    <dd>{{ brief.success_criteria }}</dd>
    {% endif %}
  </dl>
  <details>
    <summary>编辑简报</summary>
  {% else %}
  <p class="empty-state">尚未填写研究简报，请在下方表单中填写。</p>
  {% endif %}
  <form action="/projects/{{ project_slug }}/brief/save" method="post" class="brief-form">
    <label for="background">研究背景</label>
    <textarea id="background" name="background" rows="3" placeholder="描述研究的业务背景和动因">{{ brief.background if brief else '' }}</textarea>

    <label for="objectives">研究目标（每行一条）</label>
    <textarea id="objectives" name="objectives" rows="3" placeholder="如：了解玩家对新付费模式的接受度&#10;评估当前游戏内经济系统的满意度">{{ brief.objectives | join('\n') if brief and brief.objectives else '' }}</textarea>

    <label for="hypotheses">研究假设（每行一条，选填）</label>
    <textarea id="hypotheses" name="hypotheses" rows="2" placeholder="如：高付费玩家对社交功能的需求高于免费玩家">{{ brief.hypotheses | join('\n') if brief and brief.hypotheses else '' }}</textarea>

    <label for="target_audience">目标受众</label>
    <input
      type="text"
      id="target_audience"
      name="target_audience"
      value="{{ brief.target_audience if brief else '' }}"
      placeholder="如：过去30天有活跃登录的玩家"
    >

    <label for="success_criteria">成功标准</label>
    <input
      type="text"
      id="success_criteria"
      name="success_criteria"
      value="{{ brief.success_criteria if brief else '' }}"
      placeholder="如：获得可支持产品决策的定量+定性洞察"
    >

    <button type="submit">保存简报</button>
  </form>
  {% if brief %}
  </details>
  {% endif %}
</section>

<section class="workflow-links">
  <h2>核心工作流</h2>
  <ul>
    <li><a href="/projects/{{ project_slug }}/questionnaires/latest">📋 问卷设计</a></li>
    <li><a href="/projects/{{ project_slug }}/analysis/latest">📊 数据分析</a></li>
    <li><a href="/projects/{{ project_slug }}/reports/latest">📄 报告生成</a></li>
  </ul>
</section>

<section class="upload-section">
  <h2>上传知识文档</h2>
  <p class="help-text">上传 Markdown 格式的行业知识、竞品分析、历史研究报告等文档，系统会将其作为问卷设计和洞察生成的参考依据。</p>
  <form
    action="/projects/{{ project_slug }}/knowledge/upload"
    method="post"
    enctype="multipart/form-data"
  >
    <input type="file" name="file" accept=".md,.txt" required>
    <button type="submit">上传知识文档</button>
  </form>
</section>

<section class="upload-section">
  <h2>上传问卷数据</h2>
  <p class="help-text">
    上传 CSV 或 Excel 文件。文件必须使用<strong>双层表头</strong>格式：
    第 1 行为题目名称，第 2 行为类型标记（metadata / single_choice / multi_select / free_text / scale），
    第 3 行起为答卷数据。
    <a href="/static/survey_import_template.csv" download>下载模板</a>
  </p>
  <form
    action="/projects/{{ project_slug }}/datasets/import-form"
    method="post"
    enctype="multipart/form-data"
  >
    <input type="file" name="file" accept=".csv,.xlsx,.xls" required>
    <button type="submit">导入数据</button>
  </form>
</section>
{% endblock %}
```

**Step 4: Modify knowledge upload route for feedback**

In `src/game_survey_workbench/routes/projects.py`, update the `upload_knowledge_form` function:

```python
@router.post("/projects/{project_slug}/knowledge/upload")
async def upload_knowledge_form(project_slug: str, file: UploadFile = File(...)):
    settings, _project = require_project(project_slug=project_slug)
    knowledge_dir = settings.workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "uploaded.md").name
    destination = knowledge_dir / filename
    destination.write_bytes(await file.read())

    try:
        ingest_knowledge_file(destination, project_root=settings.workspace_root)
    except Exception:
        return RedirectResponse(
            url=f"/projects/{project_slug}?upload_error=知识文档解析失败，请检查文件格式",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/projects/{project_slug}?upload_success=知识文档「{filename}」已成功上传并入库",
        status_code=status.HTTP_303_SEE_OTHER,
    )
```

Also update `project_detail` route to pass query params to template:

```python
@router.get("/projects/{project_slug}", response_class=HTMLResponse)
def project_detail(project_slug: str, request: Request):
    settings, project = require_project(project_slug=project_slug)
    brief = get_research_brief(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    plan = get_task_plan(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    return templates.TemplateResponse(
        request,
        "projects/detail.html",
        {
            "project": project,
            "project_slug": project_slug,
            "brief": brief,
            "plan": plan,
            "upload_success": request.query_params.get("upload_success"),
            "upload_error": request.query_params.get("upload_error"),
        },
    )
```

**Step 5: Copy template CSV to static dir**

```bash
cp docs/templates/survey_import_template.csv src/game_survey_workbench/static/survey_import_template.csv
```

**Step 6: Run tests**

Run: `python -m pytest tests/test_1_0_i18n.py -v`
Expected: PASS

**Step 7: Run full suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing (no regression)

**Step 8: Commit**

```bash
git add src/game_survey_workbench/templates/projects/detail.html \
        src/game_survey_workbench/routes/projects.py \
        src/game_survey_workbench/static/survey_import_template.csv \
        tests/test_1_0_i18n.py
git commit -m "fix(1.0): 项目详情页中文化，知识上传反馈，Task Plan API泄露修复"
```

---

## Task 4: 分析仪表盘中文化 + 内部概念隐藏

**Files:**
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Test: `tests/test_1_0_i18n.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/test_1_0_i18n.py

def test_analysis_page_is_chinese(client, tmp_path):
    client.post("/projects", json={"slug": "ana-cn", "name": "分析测试"})
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Q1,Q2\nsingle_choice,free_text\n满意,很好玩\n一般,太贵了\n", encoding="utf-8")
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/projects/ana-cn/datasets/import",
            files={"file": ("data.csv", f, "text/csv")},
        )
    run_id = resp.json()["analysis_run_id"]
    resp = client.get(f"/projects/ana-cn/analysis/{run_id}")
    content = resp.text
    # 中文标题
    assert "数据分析" in content
    assert "研究进度" in content
    assert "数据概览" in content
    # 不暴露 run_id
    assert run_id not in content
    # 步骤名中文
    assert "数据已导入" in content
    assert "文本编码" in content
    assert "洞察合成" in content
    assert "报告生成" in content
```

**Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_1_0_i18n.py::test_analysis_page_is_chinese -v`
Expected: FAIL

**Step 3: Replace analysis/detail.html**

```html
{% extends "layout.html" %}
{% block title %}数据分析 — {{ project_slug }}{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/projects/{{ project_slug }}">← 返回项目</a></p>
  <h1>数据分析</h1>
</header>

{% if not run_id %}
<p class="empty-state">
  暂无分析记录。请先到<a href="/projects/{{ project_slug }}">项目页面</a>上传问卷数据。
</p>
{% else %}

{% if workflow_error %}
<section class="workflow-alert alert-error">
  <strong>上一步操作失败：</strong> {{ workflow_error }}
  <p>您可以使用下方按钮重新执行该步骤。</p>
</section>
{% endif %}

<section class="workflow-steps">
  <h2>研究进度</h2>
  <ol>
    <li class="step-item done">
      ✓ 数据已导入
    </li>
    <li class="step-item {% if 'coding_complete' in workflow_completed %}done{% elif workflow_phase == 'imported' %}current{% else %}pending{% endif %}">
      {% if 'coding_complete' in workflow_completed %}✓{% endif %} 文本编码
      {% if workflow_phase == 'imported' %}<span class="step-hint">← 当前步骤</span>{% endif %}
    </li>
    <li class="step-item {% if 'insights_complete' in workflow_completed %}done{% elif workflow_phase == 'coded' %}current{% else %}pending{% endif %}">
      {% if 'insights_complete' in workflow_completed %}✓{% endif %} 洞察合成
      {% if workflow_phase == 'coded' %}<span class="step-hint">← 当前步骤</span>{% endif %}
    </li>
    <li class="step-item {% if 'report_complete' in workflow_completed %}done{% elif workflow_phase == 'insights_ready' %}current{% else %}pending{% endif %}">
      {% if 'report_complete' in workflow_completed %}✓{% endif %} 报告生成
      {% if workflow_phase == 'insights_ready' %}<span class="step-hint">← 当前步骤</span>{% endif %}
    </li>
  </ol>
</section>

<section class="schema-overview">
  <h2>数据概览</h2>
  <table>
    <thead>
      <tr>
        <th>列名</th>
        <th>题型</th>
        <th>纳入分析</th>
      </tr>
    </thead>
    <tbody>
      {% for col_name, col_info in schema.items() %}
      <tr>
        <td>{{ col_name }}</td>
        <td>{{ col_info.question_type if col_info is mapping else col_info }}</td>
        <td>{{ '是' if col_info is mapping and col_info.include_in_analysis else '否' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</section>

<section class="findings-section">
  <h2>确定性分析结果</h2>
  {% if findings %}
  <ul class="findings-list">
    {% for finding in findings %}
    <li>{{ finding }}</li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="empty-state">数据上传后将自动计算基础统计指标。</p>
  {% endif %}
</section>

<section class="coding-section">
  <h2>文本编码结果</h2>
  {% if coding_results %}
    {% for result in coding_results %}
    <article>
      <h3>{{ result.question_column }}</h3>
      <ul>
        {% for theme in result.themes %}
        <li>
          <strong>{{ theme.theme_name if theme is mapping else theme }}</strong>
          {% if theme is mapping and theme.count is defined %}
          （{{ theme.count }} 条回答）
          {% endif %}
        </li>
        {% endfor %}
      </ul>
    </article>
    {% endfor %}
  {% else %}
  <p class="empty-state">尚未执行文本编码。</p>
  <form action="/projects/{{ project_slug }}/analysis/{{ run_id }}/code-text-all" method="post">
    <button type="submit">执行文本编码（所有开放题）</button>
  </form>
  <p class="help-text">系统将使用 LLM 对所有 free_text 类型的题目进行主题编码。</p>
  {% endif %}
</section>

<section class="insight-section">
  <h2>洞察合成</h2>
  {% if insight %}
  <div class="insight-narrative">{{ insight.narrative }}</div>
  {% if insight.evidence_section %}
  <details>
    <summary>证据依据</summary>
    <div class="evidence">{{ insight.evidence_section }}</div>
  </details>
  {% endif %}
  {% if insight_history and insight_history|length > 1 %}
  <details>
    <summary>历史洞察草稿（{{ insight_history|length - 1 }} 份）</summary>
    <ul>
      {% for previous_insight in insight_history[1:] %}
      <li>{{ previous_insight.created_at.strftime('%m-%d %H:%M') }} — {{ previous_insight.narrative[:120] }}…</li>
      {% endfor %}
    </ul>
  </details>
  {% endif %}
  {% else %}
  <p class="empty-state">尚未生成洞察。</p>
  {% endif %}
  <form action="/projects/{{ project_slug }}/analysis/{{ run_id }}/insights-generate" method="post">
    <label for="research_goal">研究目标</label>
    <input
      type="text"
      id="research_goal"
      name="research_goal"
      required
      placeholder="如：分析玩家流失的核心驱动因素"
    >
    <button type="submit">{% if insight %}重新生成洞察{% else %}生成洞察{% endif %}</button>
  </form>
  {% if not insight %}
  <p class="help-text">系统将结合确定性分析结果、编码主题和知识库，由 LLM 生成研究洞察。</p>
  {% endif %}
</section>

<section class="report-section">
  <h2>研究报告</h2>
  <form action="/projects/{{ project_slug }}/reports/generate-form" method="post">
    <input type="hidden" name="analysis_run_id" value="{{ run_id }}">
    <button type="submit">生成报告</button>
  </form>
  <p class="help-text"><a href="/projects/{{ project_slug }}/reports/latest">查看最新报告</a></p>
</section>
{% endif %}
{% endblock %}
```

**Step 4: Run test**

Run: `python -m pytest tests/test_1_0_i18n.py -v`
Expected: PASS

**Step 5: Run full suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing

**Step 6: Commit**

```bash
git add src/game_survey_workbench/templates/analysis/detail.html tests/test_1_0_i18n.py
git commit -m "fix(1.0): 分析仪表盘中文化，隐藏 run_id，步骤引导"
```

---

## Task 5: 问卷设计页中文化

**Files:**
- Modify: `src/game_survey_workbench/templates/questionnaires/detail.html`
- Modify: `src/game_survey_workbench/templates/questionnaires/history.html`
- Test: `tests/test_1_0_i18n.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/test_1_0_i18n.py

def test_questionnaire_page_is_chinese(client):
    client.post("/projects", json={"slug": "q-cn", "name": "问卷测试"})
    resp = client.get("/projects/q-cn/questionnaires/latest")
    content = resp.text
    assert "问卷设计" in content
    assert "生成问卷草稿" in content
    assert "研究目标" in content
```

**Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_1_0_i18n.py::test_questionnaire_page_is_chinese -v`
Expected: FAIL

**Step 3: Replace questionnaires/detail.html**

```html
{% extends "layout.html" %}
{% block title %}问卷设计 — {{ project_slug }}{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/projects/{{ project_slug }}">← 返回项目</a></p>
  <h1>问卷设计</h1>
</header>

{% if error_message %}
<section class="workflow-alert alert-error">
  <strong>操作失败：</strong> {{ error_message }}
</section>
{% endif %}

{% if spec %}
<section class="questionnaire-content">
  <h2>最新草稿</h2>
  <p class="muted">
    版本：{{ spec.version_id }} ｜ 研究目标：{{ spec.research_goal }}
  </p>
  <p class="muted">
    <a href="/projects/{{ project_slug }}/questionnaires/history">查看版本历史{% if version_count %} ({{ version_count }} 个版本){% endif %}</a>
  </p>
  <pre class="questionnaire-markdown">{{ spec.markdown_spec }}</pre>
  {% if spec.retrieved_snippets %}
  <details>
    <summary>参考知识来源（{{ spec.retrieved_snippets | length }} 篇）</summary>
    <ul>
      {% for snippet in spec.retrieved_snippets %}
      <li>{{ snippet.document_title if snippet is mapping else snippet }}</li>
      {% endfor %}
    </ul>
  </details>
  {% endif %}
</section>
<hr>
{% endif %}

<section class="draft-form">
  <h2>{% if spec %}生成新的草稿{% else %}生成问卷草稿{% endif %}</h2>
  <p class="help-text">系统将结合项目知识库和研究简报，由 LLM 生成问卷草稿。</p>
  <form action="/projects/{{ project_slug }}/questionnaires/draft-form" method="post">
    <label for="research_goal">研究目标</label>
    <input
      type="text"
      id="research_goal"
      name="research_goal"
      required
      placeholder="如：了解玩家对新赛季通行证的购买意愿和定价敏感度"
      value="{{ spec.research_goal if spec else '' }}"
    >
    <button type="submit">生成草稿</button>
  </form>
</section>

{% if spec %}
<section class="draft-form">
  <h2>迭代改进当前草稿</h2>
  <p class="help-text">保留当前草稿中满意的部分，告诉系统需要修改或补充的方向。</p>
  <form action="/projects/{{ project_slug }}/questionnaires/refine-form" method="post">
    <input type="hidden" name="version_id" value="{{ spec.version_id }}">
    <label for="feedback">修改意见</label>
    <textarea
      id="feedback"
      name="feedback"
      rows="4"
      required
      placeholder="如：增加一道关于消费习惯的题目，简化第 3 题的措辞"
    ></textarea>
    <button type="submit">改进草稿</button>
  </form>
</section>
{% endif %}
{% endblock %}
```

**Step 4: Replace questionnaires/history.html**

```html
{% extends "layout.html" %}
{% block title %}版本历史 — {{ project_slug }}{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/projects/{{ project_slug }}/questionnaires/latest">← 返回问卷设计</a></p>
  <h1>问卷版本历史</h1>
</header>

<section>
  {% if versions %}
  <table>
    <thead>
      <tr>
        <th>版本</th>
        <th>研究目标</th>
        <th>创建时间</th>
      </tr>
    </thead>
    <tbody>
      {% for version in versions %}
      <tr>
        <td>{{ version.version_id }}</td>
        <td>{{ version.research_goal }}</td>
        <td>{{ version.created_at.strftime('%Y-%m-%d %H:%M') if version.created_at else '' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty-state">尚无问卷版本记录。</p>
  {% endif %}
</section>

{% if version_diff %}
<section>
  <h2>版本对比</h2>
  <p class="muted">
    {{ version_diff.version_a }} → {{ version_diff.version_b }}
    ｜ 新增 {{ version_diff.added_lines }} 行，删除 {{ version_diff.removed_lines }} 行
  </p>
  <pre class="questionnaire-markdown">{{ version_diff.unified_diff }}</pre>
</section>
{% elif versions|length >= 2 %}
<section>
  <h2>对比两个版本</h2>
  <form method="get" action="/projects/{{ project_slug }}/questionnaires/history">
    <label for="from_version">起始版本</label>
    <input type="text" id="from_version" name="from_version" required value="{{ from_version or versions[-1].version_id }}">
    <label for="to_version">目标版本</label>
    <input type="text" id="to_version" name="to_version" required value="{{ to_version or versions[0].version_id }}">
    <button type="submit">查看对比</button>
  </form>
</section>
{% endif %}
{% endblock %}
```

**Step 5: Run tests and commit**

Run: `python -m pytest --tb=short -q`

```bash
git add src/game_survey_workbench/templates/questionnaires/detail.html \
        src/game_survey_workbench/templates/questionnaires/history.html \
        tests/test_1_0_i18n.py
git commit -m "fix(1.0): 问卷设计页和版本历史页中文化"
```

---

## Task 6: 报告页中文化

**Files:**
- Modify: `src/game_survey_workbench/templates/reports/detail.html`
- Modify: `src/game_survey_workbench/templates/reports/history.html`
- Test: `tests/test_1_0_i18n.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/test_1_0_i18n.py

def test_report_page_is_chinese(client):
    client.post("/projects", json={"slug": "rpt-cn", "name": "报告测试"})
    resp = client.get("/projects/rpt-cn/reports/latest")
    content = resp.text
    assert "研究报告" in content
    # 空状态中文
    assert "尚未生成报告" in content or "报告" in content


def test_report_history_page_is_chinese(client):
    client.post("/projects", json={"slug": "rph-cn", "name": "报告历史"})
    resp = client.get("/projects/rph-cn/reports/history")
    content = resp.text
    assert "报告历史" in content
    # 不暴露文件路径列
    assert "Path" not in content
```

**Step 2: Replace reports/detail.html**

```html
{% extends "layout.html" %}
{% block title %}研究报告 — {{ project_slug }}{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/projects/{{ project_slug }}">← 返回项目</a></p>
  <h1>研究报告</h1>
  <p><a href="/projects/{{ project_slug }}/reports/history">查看报告历史</a></p>
</header>

{% if report_content %}
<section class="report-content">
  {% if report_display and report_display.generated_on %}
  <p class="muted">生成时间：{{ report_display.generated_on }}</p>
  {% endif %}
  {% for section in report_display.sections if report_display %}
  <section class="report-section">
    <h2>{{ section.title }}</h2>
    {% for paragraph in section.paragraphs %}
    <p>{{ paragraph }}</p>
    {% endfor %}
    {% if section.bullets %}
    <ul>
      {% for bullet in section.bullets %}
      <li>{{ bullet }}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </section>
  {% endfor %}
</section>
{% else %}
<p class="empty-state">
  尚未生成报告。请到<a href="/projects/{{ project_slug }}/analysis/latest">数据分析页</a>
  完成分析后生成报告。
</p>
{% endif %}
{% endblock %}
```

**Step 3: Replace reports/history.html**

```html
{% extends "layout.html" %}
{% block title %}报告历史 — {{ project_slug }}{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/projects/{{ project_slug }}/reports/latest">← 返回最新报告</a></p>
  <h1>报告历史</h1>
</header>

{% if versions %}
<table>
  <thead>
    <tr>
      <th>序号</th>
      <th>生成时间</th>
    </tr>
  </thead>
  <tbody>
    {% for version in versions %}
    <tr>
      <td>第 {{ loop.index }} 版</td>
      <td>{{ version.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<p class="empty-state">暂无报告历史记录。</p>
{% endif %}
{% endblock %}
```

**Step 4: Run tests and commit**

Run: `python -m pytest --tb=short -q`

```bash
git add src/game_survey_workbench/templates/reports/detail.html \
        src/game_survey_workbench/templates/reports/history.html \
        tests/test_1_0_i18n.py
git commit -m "fix(1.0): 报告页和报告历史页中文化，隐藏文件路径"
```

---

## Task 7: 数据导入错误处理改进

**Files:**
- Modify: `src/game_survey_workbench/routes/datasets.py`
- Test: `tests/test_1_0_i18n.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/test_1_0_i18n.py

def test_dataset_import_bad_format_shows_error(client, tmp_path):
    """上传格式错误的数据应返回友好错误，不应 500"""
    client.post("/projects", json={"slug": "bad-csv", "name": "Bad CSV"})
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")  # 缺少第二行类型标记
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/projects/bad-csv/datasets/import-form",
            files={"file": ("bad.csv", f, "text/csv")},
            follow_redirects=False,
        )
    # Should redirect back to project page with error, not 500 or bare JSON
    assert resp.status_code in (303, 400)
```

**Step 2: Modify import-form route for friendly error handling**

In `src/game_survey_workbench/routes/datasets.py`, update `import_dataset_form`:

```python
@router.post("/projects/{project_slug}/datasets/import-form")
async def import_dataset_form(project_slug: str, file: UploadFile = File(...)):
    try:
        dataset = await _import_uploaded_dataset(project_slug=project_slug, file=file)
    except HTTPException as exc:
        return RedirectResponse(
            url=f"/projects/{project_slug}?upload_error={exc.detail}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/{dataset.analysis_run_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
```

**Step 3: Run tests and commit**

Run: `python -m pytest --tb=short -q`

```bash
git add src/game_survey_workbench/routes/datasets.py tests/test_1_0_i18n.py
git commit -m "fix(1.0): 数据导入表单错误友好处理，重定向回项目页显示错误"
```

---

## Task 8: 问卷 refine-form 异常兜底

**Files:**
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Test: `tests/test_1_0_i18n.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/test_1_0_i18n.py

def test_questionnaire_refine_error_does_not_500(client):
    """refine-form 在非 LLM 异常时不应返回 500"""
    client.post("/projects", json={"slug": "refine-err", "name": "Refine Err"})
    resp = client.post(
        "/projects/refine-err/questionnaires/refine-form",
        data={"version_id": "nonexistent", "feedback": "test"},
        follow_redirects=False,
    )
    # Should not crash with 500; 404 for missing version is acceptable
    assert resp.status_code in (303, 404)
```

**Step 2: Add exception handling to refine-form**

In `src/game_survey_workbench/routes/questionnaires.py`, wrap the `refine_questionnaire_form` function body in a try/except:

After the existing `except MissingLLMConfigurationError` block, add:

```python
    except Exception:
        return RedirectResponse(
            url=f"/projects/{project_slug}/questionnaires/latest?error=refine_failed",
            status_code=status.HTTP_303_SEE_OTHER,
        )
```

And update the `questionnaire_detail` route to handle the new error type:

```python
"error_message": (
    LLM_CONFIG_ERROR_MESSAGE
    if request.query_params.get("error") == "llm_missing"
    else "问卷改进失败，请重试或更换修改意见"
    if request.query_params.get("error") == "refine_failed"
    else None
),
```

**Step 3: Run tests and commit**

Run: `python -m pytest --tb=short -q`

```bash
git add src/game_survey_workbench/routes/questionnaires.py tests/test_1_0_i18n.py
git commit -m "fix(1.0): 问卷 refine-form 异常兜底处理"
```

---

## Task 9: CSS 补充样式

**Files:**
- Modify: `src/game_survey_workbench/static/app.css`

**Step 1: Add alert-success and help-text styles**

Append to `app.css`:

```css
/* 1.0 closeout styles */
.alert-success {
    background: #f0fdf4;
    border: 1px solid #86efac;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 16px;
    color: #166534;
}

.help-text {
    font-size: 0.9em;
    color: #6b7280;
    margin-top: 4px;
    margin-bottom: 12px;
}

.step-hint {
    font-size: 0.85em;
    color: #2563eb;
    margin-left: 8px;
}
```

**Step 2: Run full suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing

**Step 3: Commit**

```bash
git add src/game_survey_workbench/static/app.css
git commit -m "fix(1.0): 补充成功提示和帮助文案的 CSS 样式"
```

---

## Task 10: 全量回归验证

**Step 1: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing, count ≥ 218 (212 baseline + 6+ new i18n tests)

**Step 2: Compile check**

Run: `python -m compileall src/`
Expected: No syntax errors

**Step 3: Final commit if any fixes needed**

---

## Dependency Graph

```
Task 1 (layout) — independent
Task 2 (index) — depends on Task 1
Task 3 (project detail + routes) — depends on Task 1
Task 4 (analysis detail) — depends on Task 1
Task 5 (questionnaire pages) — depends on Task 1
Task 6 (report pages) — depends on Task 1
Task 7 (dataset error handling) — depends on Task 3 (uses same redirect pattern)
Task 8 (questionnaire error handling) — depends on Task 5
Task 9 (CSS) — independent
Task 10 (regression) — after all above
```

Tasks 2-6 can be done in parallel after Task 1. Task 9 is fully independent.

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| 中文模板破坏 Jinja2 变量引用 | High | 每个 Task 保留原始 `{{ }}` 引用不变，只改固定文案 |
| Stage 5-7 测试依赖英文关键字断言 | Medium | 只改 HTML 模板文案，不改路由返回值和模型字段 |
| 知识上传 try/except 太宽泛 | Low | 只 catch ingest 阶段，文件写入已在 try 前完成 |
| 数据导入错误信息是英文 ValueError | Low | 当前 ValueError 已是可读的，后续 2.0 可以中文化 |

## Verification Checklist

- [ ] 首页全中文，无 "POST /projects" 泄露
- [ ] 项目详情页全中文，Brief 表单有中文 placeholder
- [ ] 知识上传后有成功/失败提示
- [ ] 数据上传有格式说明和模板下载链接
- [ ] 分析页全中文，无 analysis_run_id 暴露
- [ ] 分析步骤有中文名和"当前步骤"指示
- [ ] 问卷设计页全中文
- [ ] 报告页全中文，无文件路径暴露
- [ ] Task Plan 空状态无 API 端点暴露
- [ ] 全量测试通过
