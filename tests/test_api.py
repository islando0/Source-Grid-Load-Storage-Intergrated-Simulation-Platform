from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["data_package_found"] is True


def test_scenarios():
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["scenarios"]]
    assert ids == ["A", "B"]
    assert all(s["hours"] == 5832 for s in r.json()["scenarios"])


def test_simulate_base():
    r = client.post(
        "/api/simulate",
        json={"scenario": "A", "C_w": 50, "C_pv": 80, "C_b": 20, "E_b": 80},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["params"]["C_pv"] == 80
    assert data["metrics"]["annual_cost"] > 0
    assert 0.0 <= data["metrics"]["curtail_rate"] <= 1.0
    assert "series" not in data


def test_simulate_series():
    r = client.post(
        "/api/simulate",
        json={"scenario": "B", "C_w": 50, "C_pv": 80, "C_b": 20, "E_b": 80, "keep_series": True},
    )
    assert r.status_code == 200
    series = r.json()["series"]
    assert len(series["soc"]) == 5832
    assert len(series["load"]) == 5832


def test_simulate_rejects_negative():
    r = client.post("/api/simulate", json={"C_w": -1})
    assert r.status_code == 422


def test_optimize_and_runs():
    r = client.post(
        "/api/optimize",
        json={"scenario": "A", "algorithm": "pso", "particles": 4, "iters": 3, "seed": 7},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["best_x"]) == 4
    assert data["run_id"] >= 1
    assert data["best_metrics"]["annual_cost"] > 0

    runs = client.get("/api/runs?limit=5")
    assert runs.status_code == 200
    assert any(item["id"] == data["run_id"] for item in runs.json()["runs"])


def test_reference():
    r = client.get("/api/reference")
    assert r.status_code == 200
    assert r.json()["available"] is True
    assert len(r.json()["best_x"]) == 4


def test_ml_model_and_compare():
    info = client.get("/api/ml/pv")
    assert info.status_code == 200
    assert info.json()["available"] is True
    assert info.json()["metrics"]["r2"] > 0.9

    compare = client.get("/api/ml/pv/compare")
    assert compare.status_code == 200
    assert compare.json()["rows"] == 5832


def test_simulate_with_ml_pv():
    r = client.post(
        "/api/simulate",
        json={"scenario": "A", "C_w": 50, "C_pv": 80, "pv_model": "ml"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["pv_model"] == "ml"
    assert data["metrics"]["annual_cost"] > 0


def test_ml_pv_rejects_scenario_b():
    r = client.post("/api/simulate", json={"scenario": "B", "pv_model": "ml"})
    assert r.status_code == 400

