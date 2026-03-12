def test_end_to_end_flow_creates_report(client, seeded_workspace):
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
    report = client.post(
        f"/projects/{project['slug']}/reports/generate",
        json={"analysis_run_id": dataset["analysis_run_id"]},
    ).json()

    assert draft["version_id"]
    assert dataset["dataset_id"]
    assert report["path"].endswith(".md")
