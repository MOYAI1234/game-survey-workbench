from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_layout_nav_is_chinese(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert "游戏问卷研究工作台" in response.text


def test_index_page_is_chinese(client: TestClient):
    response = client.get("/")
    content = response.text

    assert "新建项目" in content
    assert "项目标识" in content
    assert "项目名称" in content
    assert "POST /projects" not in content
    assert "Create New Project" not in content
    assert "Slug (URL identifier)" not in content


def test_index_empty_state_chinese(client: TestClient):
    response = client.get("/")

    assert "暂无项目" in response.text
    assert "POST /projects" not in response.text


def test_project_detail_is_chinese(client: TestClient):
    client.post("/projects", json={"slug": "test-cn", "name": "中文测试"})

    response = client.get("/projects/test-cn")
    content = response.text

    assert "研究简报" in content
    assert "研究背景" in content
    assert "研究目标" in content
    assert "上传知识文档" in content
    assert "上传问卷数据" in content
    assert "PUT /projects/" not in content
    assert "双层表头" in content
    assert "当前版本不会自动生成任务计划" in content
    assert "任务计划会在你完善研究简报后逐步明确" not in content


def test_knowledge_upload_has_feedback(client: TestClient, tmp_path: Path):
    client.post("/projects", json={"slug": "kb-test", "name": "KB Test"})
    md_file = tmp_path / "test_knowledge.md"
    md_file.write_text("# Test Knowledge\n\nSome content here.", encoding="utf-8")

    with md_file.open("rb") as handle:
        response = client.post(
            "/projects/kb-test/knowledge/upload",
            files={"file": ("test.md", handle, "text/markdown")},
            follow_redirects=False,
        )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "upload_success=" in location or "success" in location.lower()


def test_analysis_page_is_chinese(client: TestClient, tmp_path: Path):
    client.post("/projects", json={"slug": "ana-cn", "name": "分析测试"})
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "Q1,Q2\nsingle_choice,free_text\n满意,很好玩\n一般,太贵了\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as handle:
        response = client.post(
            "/projects/ana-cn/datasets/import",
            files={"file": ("data.csv", handle, "text/csv")},
        )

    run_id = response.json()["analysis_run_id"]
    response = client.get(f"/projects/ana-cn/analysis/{run_id}")
    content = response.text

    assert "数据分析" in content
    assert "研究进度" in content
    assert "数据概览" in content
    assert run_id not in content
    assert "数据已导入" in content
    assert "文本编码" in content
    assert "洞察合成" in content
    assert "报告生成" in content


def test_questionnaire_page_is_chinese(client: TestClient):
    client.post("/projects", json={"slug": "q-cn", "name": "问卷测试"})

    response = client.get("/projects/q-cn/questionnaires/latest")
    content = response.text

    assert "问卷设计" in content
    assert "生成问卷草稿" in content
    assert "研究目标" in content


def test_report_page_is_chinese(client: TestClient):
    client.post("/projects", json={"slug": "rpt-cn", "name": "报告测试"})

    response = client.get("/projects/rpt-cn/reports/latest")
    content = response.text

    assert "研究报告" in content
    assert "尚未生成报告" in content or "报告" in content


def test_report_history_page_is_chinese(client: TestClient):
    client.post("/projects", json={"slug": "rph-cn", "name": "报告历史"})

    response = client.get("/projects/rph-cn/reports/history")
    content = response.text

    assert "报告历史" in content
    assert "Path" not in content


def test_dataset_import_bad_format_shows_error(client: TestClient, tmp_path: Path):
    client.post("/projects", json={"slug": "bad-csv", "name": "Bad CSV"})
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")

    with csv_path.open("rb") as handle:
        response = client.post(
            "/projects/bad-csv/datasets/import-form",
            files={"file": ("bad.csv", handle, "text/csv")},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "upload_error=" in response.headers["location"]


def test_questionnaire_refine_error_does_not_500(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with TestClient(create_app()) as client:
        client.post("/projects", json={"slug": "refine-err", "name": "Refine Err"})
        with Session(engine) as session:
            session.add(
                QuestionnaireSpecVersion(
                    project_slug="refine-err",
                    version_id="v1",
                    research_goal="baseline",
                    markdown_spec="# Draft\n\n1. Question",
                    citations=[],
                    retrieved_snippets=[],
                )
            )
            session.commit()

        from game_survey_workbench.routes import questionnaires as questionnaires_module

        def _raise_unexpected(*args, **kwargs):
            raise RuntimeError("unexpected refine failure")

        monkeypatch.setattr(
            questionnaires_module,
            "refine_questionnaire_draft",
            _raise_unexpected,
        )

        response = client.post(
            "/projects/refine-err/questionnaires/refine-form",
            data={"version_id": "v1", "feedback": "test"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert "error=refine_failed" in response.headers["location"]
