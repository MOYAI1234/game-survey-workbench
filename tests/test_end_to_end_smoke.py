from game_survey_workbench.llm.client import OpenAICompatibleLLMClient
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


def test_end_to_end_flow_creates_report(client, seeded_workspace, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    def fake_generate(self, prompt: str):
        if "Open Text Coding Prompt" in prompt:
            return (
                '{"themes": [{"theme_name": "Boredom", "count": 2, '
                '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 1}'
            )
        if "Insight Synthesis Prompt" in prompt:
            return "Boredom emerged as the dominant churn factor based on the coded themes and knowledge."
        return "# Questionnaire Draft\n\n## Core Questions\n- Why did you return?"

    monkeypatch.setattr(OpenAICompatibleLLMClient, "generate", fake_generate)
    for source in (seeded_workspace / "knowledge").glob("*.md"):
        ingest_knowledge_file(source, project_root=seeded_workspace)

    project = client.post("/projects", json={"slug": "demo", "name": "Demo", "knowledge_pack": {}}).json()
    draft = client.post(
        f"/projects/{project['slug']}/questionnaires/draft",
        json={"research_goal": "Learn why players drop after the patch"},
    ).json()
    dataset_file = seeded_workspace / "projects" / "demo" / "data" / "raw" / "dataset.csv"
    dataset = client.post(
        f"/projects/{project['slug']}/datasets/import",
        files={"file": ("dataset.csv", dataset_file.read_text(encoding="utf-8"), "text/csv")},
    ).json()
    coding = client.post(
        f"/projects/{project['slug']}/analysis/{dataset['analysis_run_id']}/code-text",
        json={
            "question_column": "Feel free to tell us what rewards you want to see in the Season Pass! You could also give us more suggestion about the game here!",
            "responses": ["got bored", "nothing to do", "idk"],
        },
    ).json()
    insights = client.post(
        f"/projects/{project['slug']}/analysis/{dataset['analysis_run_id']}/insights",
        json={"research_goal": "Learn why players drop after the patch"},
    ).json()
    report = client.post(
        f"/projects/{project['slug']}/reports/generate",
        json={"analysis_run_id": dataset["analysis_run_id"]},
    ).json()
    report_path = seeded_workspace / report["path"]
    report_markdown = report_path.read_text(encoding="utf-8")

    assert draft["version_id"]
    assert dataset["dataset_id"]
    assert "标记" not in dataset["question_columns"]
    assert "时间戳记" not in dataset["question_columns"]
    assert dataset["question_columns"]["What are your most satisfying parts of Season Pass?"]["question_type"] == "multi_select"
    assert (
        dataset["question_columns"][
            "Feel free to tell us what rewards you want to see in the Season Pass! You could also give us more suggestion about the game here!"
        ]["question_type"]
        == "free_text"
    )
    assert report["analysis_run_id"] == dataset["analysis_run_id"]
    assert report["path"].endswith(".md")
    assert coding["themes"][0]["theme_name"] == "Boredom"
    assert "## Evidence Basis" not in insights["narrative"]
    assert insights["evidence_section"].startswith("## Evidence Basis")
    assert "Churn" in insights["citations"][0]["document_title"] or insights["citations"]
    assert report_markdown.count("## Evidence Basis") == 1
    assert "Boredom emerged as the dominant churn factor" in report_markdown
