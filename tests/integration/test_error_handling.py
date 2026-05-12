import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def create_user(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/users",
        json={
            "email": f"user-{uuid.uuid4()}@example.com",
            "password": "123456",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


async def create_account(
    client: AsyncClient,
    user_id: str,
    provider: str,
) -> str:
    response = await client.post(
        "/api/v1/accounts",
        json={
            "user_id": user_id,
            "email": f"mailbox-{uuid.uuid4()}@example.com",
            "provider": provider,
            "imap_host": "fake-imap.local",
            "imap_port": 993,
            "smtp_host": "fake-smtp.local",
            "smtp_port": 587,
            "secret": "test-secret",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


@pytest.mark.asyncio
async def test_unknown_provider_sync_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        user_id = await create_user(client)
        account_id = await create_account(client, user_id, provider="unknown")

        response = await client.post(f"/api/v1/accounts/{account_id}/sync")

        assert response.status_code == 400
        assert response.json()["detail"] == "Only fake and imap providers are supported at this stage"


@pytest.mark.asyncio
async def test_unknown_provider_send_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        user_id = await create_user(client)
        account_id = await create_account(client, user_id, provider="unknown")

        response = await client.post(
            f"/api/v1/accounts/{account_id}/send",
            data={
                "recipients": "team@example.com",
                "subject": "Unsupported provider test",
                "body_text": "This should fail.",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Only fake and imap providers are supported at this stage"


@pytest.mark.asyncio
async def test_send_with_empty_recipients_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        user_id = await create_user(client)
        account_id = await create_account(client, user_id, provider="fake")

        response = await client.post(
            f"/api/v1/accounts/{account_id}/send",
            data={
                "recipients": "   ",
                "subject": "Empty recipients test",
                "body_text": "This should fail.",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "At least one recipient is required"


@pytest.mark.asyncio
async def test_message_actions_for_unknown_message_return_404():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        message_id = uuid.uuid4()

        get_response = await client.get(f"/api/v1/messages/{message_id}")

        assert get_response.status_code == 404

        read_response = await client.patch(
            f"/api/v1/messages/{message_id}/read",
            json={
                "is_read": True,
            },
        )

        assert read_response.status_code == 404

        star_response = await client.patch(
            f"/api/v1/messages/{message_id}/star",
            json={
                "is_starred": True,
            },
        )

        assert star_response.status_code == 404

        delete_response = await client.delete(f"/api/v1/messages/{message_id}")

        assert delete_response.status_code == 404

        restore_response = await client.patch(f"/api/v1/messages/{message_id}/restore")

        assert restore_response.status_code == 404