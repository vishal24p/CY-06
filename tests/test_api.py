from fastapi.testclient import TestClient

from cy06.api import app


def test_health_endpoint():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_endpoint_returns_report():
    response = TestClient(app).post(
        "/api/v1/analyze",
        json={
            "inventory": {
                "UserDetailList": [],
                "GroupDetailList": [],
                "RoleDetailList": [],
                "Policies": [],
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["summary"]["findings"] == 0
    assert response.json()["graph"] == {"nodes": [], "edges": []}
    assert response.json()["coverage"] == {
        "identity_metadata": 0,
        "resource_policies": 0,
        "boundaries": 0,
        "scp_policies": 0,
        "sessions": 0,
    }


def test_analyze_endpoint_rejects_invalid_inventory():
    response = TestClient(app).post(
        "/api/v1/analyze",
        json={"inventory": {"RoleDetailList": "invalid"}},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "RoleDetailList must be a list"
