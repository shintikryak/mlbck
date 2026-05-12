import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def create_message(client: AsyncClient) -> str:
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

    messages_response = await client.get(
        f"/api/v1/accounts/{account_id}/messages",
        params={
            "limit": 1,
            "offset": 0,
        },
    )

    assert messages_response.status_code == 200

    return messages_response.json()["items"][0]["id"]


@pytest.mark.asyncio
async def test_manual_attachment_upload_list_and_download():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        message_id = await create_message(client)

        upload_response = await client.post(
            f"/api/v1/messages/{message_id}/attachments",
            files={
                "file": ("manual-test.txt", b"manual attachment content", "text/plain"),
            },
        )

        assert upload_response.status_code == 201

        attachment = upload_response.json()
        attachment_id = attachment["id"]

        assert attachment["message_id"] == message_id
        assert attachment["filename"] == "manual-test.txt"
        assert attachment["content_type"] == "text/plain"
        assert attachment["size_bytes"] == len(b"manual attachment content")

        list_response = await client.get(f"/api/v1/messages/{message_id}/attachments")

        assert list_response.status_code == 200

        attachments = list_response.json()

        assert len(attachments) == 1
        assert attachments[0]["id"] == attachment_id

        download_response = await client.get(
            f"/api/v1/attachments/{attachment_id}/download"
        )

        assert download_response.status_code == 200
        assert download_response.content == b"manual attachment content"


@pytest.mark.asyncio
async def test_unknown_attachment_download_returns_404():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/attachments/{uuid.uuid4()}/download")

        assert response.status_code == 404