import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_returns_components_status():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] in {"ok", "degraded"}
    assert data["components"]["api"] == "ok"
    assert "database" in data["components"]
    assert "object_storage" in data["components"]


@pytest.mark.asyncio
async def test_info_returns_project_features():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/info")

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Mailback"
    assert "features" in data
    assert "Real IMAP synchronization" in data["features"]
    assert "Real SMTP sending" in data["features"]
    assert "Encrypted mailbox credentials" in data["features"]