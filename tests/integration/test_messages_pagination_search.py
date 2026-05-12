import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def create_synced_fake_account(client: AsyncClient) -> str:
    user_response = await client.post(
        "/api/v1/users",
        json={
            "email": f"user-{uuid.uuid4()}@example.com",
            "password": "123456",
        },
    )

    assert user_response.status_code == 201

    user_id = user_response.json()["id"]

    account_response = await client.post(
        "/api/v1/accounts",
        json={
            "user_id": user_id,
            "email": f"mailbox-{uuid.uuid4()}@example.com",
            "provider": "fake",
            "imap_host": "fake-imap.local",
            "imap_port": 993,
            "smtp_host": "fake-smtp.local",
            "smtp_port": 587,
            "secret": "test-secret",
        },
    )

    assert account_response.status_code == 201

    account_id = account_response.json()["id"]

    sync_response = await client.post(f"/api/v1/accounts/{account_id}/sync")

    assert sync_response.status_code == 200

    return account_id


@pytest.mark.asyncio
async def test_messages_pagination_returns_different_pages():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        account_id = await create_synced_fake_account(client)

        first_page_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "limit": 1,
                "offset": 0,
            },
        )

        assert first_page_response.status_code == 200

        first_page = first_page_response.json()

        assert first_page["total"] == 3
        assert first_page["limit"] == 1
        assert first_page["offset"] == 0
        assert len(first_page["items"]) == 1

        second_page_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "limit": 1,
                "offset": 1,
            },
        )

        assert second_page_response.status_code == 200

        second_page = second_page_response.json()

        assert second_page["total"] == 3
        assert second_page["limit"] == 1
        assert second_page["offset"] == 1
        assert len(second_page["items"]) == 1

        assert first_page["items"][0]["id"] != second_page["items"][0]["id"]


@pytest.mark.asyncio
async def test_messages_search_by_subject_sender_recipient_and_body():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        account_id = await create_synced_fake_account(client)

        subject_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "query": "Welcome",
                "limit": 10,
                "offset": 0,
            },
        )

        assert subject_response.status_code == 200
        assert subject_response.json()["total"] >= 1

        sender_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "query": "support@mailback.local",
                "limit": 10,
                "offset": 0,
            },
        )

        assert sender_response.status_code == 200
        assert sender_response.json()["total"] >= 1

        body_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "query": "synchronized email message",
                "limit": 10,
                "offset": 0,
            },
        )

        assert body_response.status_code == 200
        assert body_response.json()["total"] >= 1

        empty_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "query": f"not-found-{uuid.uuid4()}",
                "limit": 10,
                "offset": 0,
            },
        )

        assert empty_response.status_code == 200
        assert empty_response.json()["total"] == 0
        assert empty_response.json()["items"] == []