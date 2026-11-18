import io

from openpyxl import load_workbook


def test_login_required(app):
    assert app.test_client().get("/api/summary").status_code == 401


def test_seed_loaded(client):
    cycles = client.get("/api/cycles").get_json()
    assert [c["label"] for c in cycles] == ["2025-26", "2024-25", "2023-24"]
    assert client.get("/api/submissions").get_json()["count"] == 120


def test_review_then_mark_item_received(client):
    run = client.post("/api/reviews", json={}).get_json()
    assert run["total"] == 120
    assert run["complete"] + run["late"] + run["missing"] + run["not_submitted"] == 120

    flagged = client.get("/api/submissions?status=missing").get_json()["results"]
    sub = flagged[0]
    reqs = {r["name"]: r["id"] for r in client.get("/api/requirements").get_json()}
    for name in sub["missing"]:
        r = client.patch(f"/api/submissions/{sub['id']}/items/{reqs[name]}", json={"present": True})
        assert r.status_code == 200
    detail = client.get(f"/api/submissions/{sub['id']}").get_json()
    assert detail["status"] in ("complete", "late")
    assert any(h["action"] == "item_received" for h in detail["history"])


def test_reminders_group_by_coordinator(client):
    client.post("/api/reviews", json={})
    rem = client.get("/api/reminders").get_json()["results"]
    assert rem and all("Hi " in g["body"] for g in rem)
    emails = [g["email"] for g in rem]
    assert len(emails) == len(set(emails))


def test_excel_exports_open(client):
    client.post("/api/reviews", json={})
    for path in ("/api/export/checklist.xlsx", "/api/export/reminders.xlsx"):
        r = client.get(path)
        assert r.status_code == 200
        wb = load_workbook(io.BytesIO(r.data))
        assert wb.worksheets[0].max_row > 1


def test_import_csv(client):
    csv_text = client.get("/import/template.csv").data
    r = client.post("/api/import", data={"file": (io.BytesIO(csv_text), "t.csv")}, content_type="multipart/form-data")
    body = r.get_json()
    assert r.status_code == 200 and body["updated"] == 3 and not body["errors"]


def test_import_rejects_bad_header(client):
    r = client.post("/api/import", data={"file": (io.BytesIO(b"foo,bar\n1,2\n"), "t.csv")}, content_type="multipart/form-data")
    assert r.status_code == 400
