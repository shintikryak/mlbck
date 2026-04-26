import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.fake_connector import FakeMailboxConnector
from app.connectors.imap_connector import ImapMailboxConnector
from app.core.config import settings
from app.models.folder import Folder
from app.models.message import Message
from app.models.sync_state import SyncState
from app.services.accounts import get_mail_account


class UnsupportedProviderError(Exception):
    pass


class MissingCredentialsError(Exception):
    pass


def build_connector(account):
    if account.provider == "fake":
        return FakeMailboxConnector(account.email)

    if account.provider == "imap":
        if not account.encrypted_secret:
            raise MissingCredentialsError

        return ImapMailboxConnector(
            email_address=account.email,
            password=account.encrypted_secret,
            host=account.imap_host,
            port=account.imap_port,
            fetch_limit=settings.imap_fetch_limit,
        )

    raise UnsupportedProviderError


async def sync_account(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> dict | None:
    account = await get_mail_account(session, account_id)

    if account is None:
        return None

    connector = build_connector(account)

    folders_created = 0
    folders_updated = 0
    messages_created = 0
    messages_updated = 0

    connector_folders = await connector.list_folders()

    for connector_folder in connector_folders:
        folder_stmt = select(Folder).where(
            Folder.account_id == account.id,
            Folder.provider_folder_id == connector_folder.provider_folder_id,
        )
        folder_result = await session.execute(folder_stmt)
        folder = folder_result.scalar_one_or_none()

        if folder is None:
            folder = Folder(
                account_id=account.id,
                provider_folder_id=connector_folder.provider_folder_id,
                name=connector_folder.name,
            )
            session.add(folder)
            await session.flush()
            folders_created += 1
        else:
            folder.name = connector_folder.name
            folders_updated += 1

        state_stmt = select(SyncState).where(
            SyncState.account_id == account.id,
            SyncState.folder_id == folder.id,
        )
        state_result = await session.execute(state_stmt)
        sync_state = state_result.scalar_one_or_none()

        checkpoint = sync_state.checkpoint if sync_state else None
        connector_messages = await connector.list_messages(
            connector_folder.provider_folder_id,
            checkpoint,
        )

        last_uid = None

        for connector_message in connector_messages:
            message_stmt = select(Message).where(
                Message.account_id == account.id,
                Message.folder_id == folder.id,
                Message.provider_message_id == connector_message.provider_message_id,
            )
            message_result = await session.execute(message_stmt)
            message = message_result.scalar_one_or_none()

            recipients = ", ".join(connector_message.recipients)
            last_uid = connector_message.provider_message_id

            if message is None:
                message = Message(
                    account_id=account.id,
                    folder_id=folder.id,
                    provider_message_id=connector_message.provider_message_id,
                    subject=connector_message.subject,
                    sender=connector_message.sender,
                    recipients=recipients,
                    body_text=connector_message.body_text,
                    sent_at=connector_message.sent_at,
                    is_read=connector_message.is_read,
                    is_starred=connector_message.is_starred,
                )
                session.add(message)
                messages_created += 1
            else:
                message.subject = connector_message.subject
                message.sender = connector_message.sender
                message.recipients = recipients
                message.body_text = connector_message.body_text
                message.sent_at = connector_message.sent_at
                message.is_read = connector_message.is_read
                message.is_starred = connector_message.is_starred
                messages_updated += 1

        now = datetime.now(timezone.utc)

        if sync_state is None:
            sync_state = SyncState(
                account_id=account.id,
                folder_id=folder.id,
                last_uid=last_uid,
                checkpoint=last_uid,
                last_synced_at=now,
            )
            session.add(sync_state)
        else:
            sync_state.last_uid = last_uid
            sync_state.checkpoint = last_uid
            sync_state.last_synced_at = now

    await session.commit()

    return {
        "account_id": account.id,
        "folders_created": folders_created,
        "folders_updated": folders_updated,
        "messages_created": messages_created,
        "messages_updated": messages_updated,
    }