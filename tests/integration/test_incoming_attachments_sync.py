import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_sync_stores_incoming_message_attachments():
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

        search_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "query": "Welcome to Mailback",
                "limit": 10,
                "offset": 0,
            },
        )

        assert search_response.status_code == 200

        messages = search_response.json()["items"]

        assert len(messages) == 1

        message_id = messages[0]["id"]

        attachments_response = await client.get(
            f"/api/v1/messages/{message_id}/attachments"
        )

        assert attachments_response.status_code == 200

        attachments = attachments_response.json()

        assert len(attachments) == 1

        attachment = attachments[0]

        assert attachment["filename"] == "welcome.txt"
        assert attachment["content_type"] == "text/plain"
        assert attachment["size_bytes"] == len(b"Welcome attachment from fake IMAP sync")

        download_response = await client.get(
            f"/api/v1/attachments/{attachment['id']}/download"
        )

        assert download_response.status_code == 200
        assert download_response.content == b"Welcome attachment from fake IMAP sync"

        second_sync_response = await client.post(f"/api/v1/accounts/{account_id}/sync")

        assert second_sync_response.status_code == 200

        second_attachments_response = await client.get(
            f"/api/v1/messages/{message_id}/attachments"
        )

        assert second_attachments_response.status_code == 200
        assert len(second_attachments_response.json()) == 1