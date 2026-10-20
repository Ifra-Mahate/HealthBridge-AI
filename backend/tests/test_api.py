from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    res = client.get("/api")
    assert res.status_code == 200
    data = res.json()
    assert data["project"] == "HealthBridge AI"


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "ai_configured" in data


def test_samples_endpoint():
    res = client.get("/api/samples")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    assert "sample_amoxicillin" in [item["id"] for item in data]


def test_extract_endpoint():
    payload = {
        "raw_text": "Amoxicillin 500 mg PO TID x 7 days with meals. Avoid alcohol.",
        "target_language": "en"
    }
    res = client.post("/api/extract", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "dosages" in data
    assert "frequencies" in data


def test_simplify_endpoint_multilingual():
    payload = {
        "raw_text": "Amoxicillin 500 mg PO TID x 7 days with meals. Do not take with alcohol. Discontinue if rash occurs.",
        "target_language": "hi"
    }
    res = client.post("/api/simplify", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["target_language"] == "hi"
    assert "structured_cards" in data
    assert "verification" in data
    assert data["verification"]["score"] > 0
