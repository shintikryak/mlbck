import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_full_fake_mail_flow():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        user_email = f"user-{uuid.uuid4()}@example.com"

        user_response = await client.post(
            "/api/v1/users",
            json={
                "email": user_email,
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

        sync_response = await client.post(f"/api/v1/accounts/{account_id}/sync")

        assert sync_response.status_code == 200

        sync_result = sync_response.json()

        assert sync_result["folders_created"] == 2
        assert sync_result["folders_updated"] == 0
        assert sync_result["messages_created"] == 3
        assert sync_result["messages_updated"] == 0

        second_sync_response = await client.post(f"/api/v1/accounts/{account_id}/sync")

        assert second_sync_response.status_code == 200

        second_sync_result = second_sync_response.json()

        assert second_sync_result["folders_created"] == 0
        assert second_sync_result["folders_updated"] == 0
        assert second_sync_result["messages_created"] == 0
        assert second_sync_result["messages_updated"] == 0

        folders_response = await client.get(f"/api/v1/accounts/{account_id}/folders")

        assert folders_response.status_code == 200

        folders = folders_response.json()

        assert len(folders) == 2

        inbox_folder = next(
            folder for folder in folders if folder["provider_folder_id"] == "INBOX"
        )
        sent_folder = next(
            folder for folder in folders if folder["provider_folder_id"] == "SENT"
        )

        messages_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "limit": 10,
                "offset": 0,
            },
        )

        assert messages_response.status_code == 200

        messages_page = messages_response.json()

        assert messages_page["total"] == 3
        assert len(messages_page["items"]) == 3
        assert messages_page["limit"] == 10
        assert messages_page["offset"] == 0

        inbox_messages_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "folder_id": inbox_folder["id"],
                "limit": 10,
                "offset": 0,
            },
        )

        assert inbox_messages_response.status_code == 200
        assert inbox_messages_response.json()["total"] == 2

        sent_messages_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "folder_id": sent_folder["id"],
                "limit": 10,
                "offset": 0,
            },
        )

        assert sent_messages_response.status_code == 200
        assert sent_messages_response.json()["total"] == 1

        search_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "query": "synchronization",
                "limit": 10,
                "offset": 0,
            },
        )

        assert search_response.status_code == 200
        assert search_response.json()["total"] >= 1

        message = messages_page["items"][0]
        message_id = message["id"]

        get_message_response = await client.get(f"/api/v1/messages/{message_id}")

        assert get_message_response.status_code == 200
        assert get_message_response.json()["id"] == message_id

        read_response = await client.patch(
            f"/api/v1/messages/{message_id}/read",
            json={
                "is_read": False,
            },
        )

        assert read_response.status_code == 200
        assert read_response.json()["is_read"] is False

        star_response = await client.patch(
            f"/api/v1/messages/{message_id}/star",
            json={
                "is_starred": True,
            },
        )

        assert star_response.status_code == 200
        assert star_response.json()["is_starred"] is True

        delete_response = await client.delete(f"/api/v1/messages/{message_id}")

        assert delete_response.status_code == 200
        assert delete_response.json()["is_deleted"] is True

        after_delete_response = await client.get(
            f"/api/v1/accounts/{account_id}/messages",
            params={
                "limit": 10,
                "offset": 0,
            },
        )

        assert after_delete_response.status_code == 200
        assert after_delete_response.json()["total"] == 2

        restore_response = await client.patch(f"/api/v1/messages/{message_id}/restore")

        assert restore_response.status_code == 200
        assert restore_response.json()["is_deleted"] is False

        send_without_attachment_response = await client.post(
            f"/api/v1/accounts/{account_id}/send",
            data={
                "recipients": "team@example.com",
                "subject": "Automated fake send test",
                "body_text": "This message was created by an integration test.",
            },
        )

        assert send_without_attachment_response.status_code == 200

        sent_message = send_without_attachment_response.json()

        assert sent_message["subject"] == "Automated fake send test"
        assert sent_message["sender"] == account_email
        assert sent_message["recipients"] == "team@example.com"
        assert sent_message["is_read"] is True

        send_with_attachment_response = await client.post(
            f"/api/v1/accounts/{account_id}/send",
            data={
                "recipients": "team@example.com",
                "subject": "Automated fake attachment test",
                "body_text": "This message has an attachment.",
            },
            files={
                "file": ("test.txt", b"hello from pytest attachment", "text/plain"),
            },
        )

        assert send_with_attachment_response.status_code == 200

        sent_with_attachment = send_with_attachment_response.json()
        sent_with_attachment_id = sent_with_attachment["id"]

        attachments_response = await client.get(
            f"/api/v1/messages/{sent_with_attachment_id}/attachments"
        )

        assert attachments_response.status_code == 200

        attachments = attachments_response.json()

        assert len(attachments) == 1

        attachment = attachments[0]
        attachment_id = attachment["id"]

        assert attachment["filename"] == "test.txt"
        assert attachment["content_type"] == "text/plain"
        assert attachment["size_bytes"] == len(b"hello from pytest attachment")

        download_response = await client.get(
            f"/api/v1/attachments/{attachment_id}/download"
        )

        assert download_response.status_code == 200
        assert download_response.content == b"hello from pytest attachment"