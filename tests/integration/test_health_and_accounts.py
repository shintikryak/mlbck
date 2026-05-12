import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_and_root():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        health_response = await client.get("/api/v1/health")

        assert health_response.status_code == 200
        assert health_response.json()["status"] == "ok"

        root_response = await client.get("/")

        assert root_response.status_code == 200


@pytest.mark.asyncio
async def test_create_and_get_account_by_id_and_user_id():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        user_response = await client.post(
            "/api/v1/users",
            json={
                "email": f"user-{uuid.uuid4()}@example.com",
                "password": "123456",
            },
        )

        assert user_response.status_code == 201

        user = user_response.json()
        user_id = user["id"]

        account_email = f"mailbox-{uuid.uuid4()}@example.com"

        account_response = await client.post(
            "/api/v1/accounts",
            json={
                "user_id": user_id,
                "email": account_email,
                "provider": "fake",
                "imap_host": "fake-imap.local",
                "imap_port": 993,
                "smtp_host": "fake-smtp.local",
                "smtp_port": 587,
                "secret": "test-secret",
            },
        )

        assert account_response.status_code == 201

        account = account_response.json()
        account_id = account["id"]

        get_by_id_response = await client.get(f"/api/v1/accounts/{account_id}")

        assert get_by_id_response.status_code == 200
        assert get_by_id_response.json()["id"] == account_id
        assert get_by_id_response.json()["user_id"] == user_id
        assert get_by_id_response.json()["email"] == account_email

        list_response = await client.get(
            "/api/v1/accounts",
            params={
                "user_id": user_id,
            },
        )

        assert list_response.status_code == 200

        accounts = list_response.json()

        assert len(accounts) == 1
        assert accounts[0]["id"] == account_id


@pytest.mark.asyncio
async def test_get_unknown_account_returns_404():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/accounts/{uuid.uuid4()}")

        assert response.status_code == 404