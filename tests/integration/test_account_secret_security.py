import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import async_session_factory
from app.main import app
from app.models.mail_account import MailAccount


@pytest.mark.asyncio
async def test_account_secret_is_encrypted_and_not_returned():
    if not settings.secret_encryption_key:
        pytest.skip("SECRET_ENCRYPTION_KEY is not configured")

    secret = "test-secret-for-encryption"

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
                "secret": secret,
            },
        )

        assert account_response.status_code == 201

        account_data = account_response.json()
        account_id = account_data["id"]

        assert "secret" not in account_data
        assert "encrypted_secret" not in account_data
        assert "password" not in account_data

        get_account_response = await client.get(f"/api/v1/accounts/{account_id}")

        assert get_account_response.status_code == 200

        get_account_data = get_account_response.json()

        assert "secret" not in get_account_data
        assert "encrypted_secret" not in get_account_data
        assert "password" not in get_account_data

    async with async_session_factory() as session:
        account = await session.get(MailAccount, uuid.UUID(account_id))

        assert account is not None
        assert account.encrypted_secret is not None
        assert account.encrypted_secret != secret
        assert account.encrypted_secret.startswith("fernet:")