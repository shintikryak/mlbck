import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorOutgoingAttachment
from app.connectors.fake_connector import FakeMailboxConnector
from app.connectors.imap_connector import ImapMailboxConnector
from app.core.config import settings
from app.core.security import decrypt_secret
from app.models.attachment import Attachment
from app.models.folder import Folder
from app.models.mail_account import MailAccount
from app.models.message import Message
from app.models.sync_state import SyncState
from app.schemas.sync import SyncResult
from app.services.accounts import get_mail_account
from app.storage.s3 import upload_file


class UnsupportedProviderError(Exception):
    pass


class MissingCredentialsError(Exception):
    pass


@dataclass
class SyncCounters:
    folders_created: int = 0
    folders_updated: int = 0
    messages_created: int = 0
    messages_updated: int = 0


def build_connector(account: MailAccount):
    if account.provider == "fake":
        return FakeMailboxConnector(account.email)

    if account.provider == "imap":
        secret = decrypt_secret(account.encrypted_secret)

        if not secret:
            raise MissingCredentialsError

        return ImapMailboxConnector(
            email_address=account.email,
            password=secret,
            host=account.imap_host,
            port=account.imap_port,
            fetch_limit=settings.imap_fetch_limit,
        )

    raise UnsupportedProviderError


async def get_or_create_folder(
    session: AsyncSession,
    account_id: uuid.UUID,
    provider_folder_id: str,
    name: str,
    counters: SyncCounters,
) -> Folder:
    stmt = select(Folder).where(
        Folder.account_id == account_id,
        Folder.provider_folder_id == provider_folder_id,
    )
    result = await session.execute(stmt)
    folder = result.scalar_one_or_none()

    if folder is None:
        folder = Folder(
            account_id=account_id,
            provider_folder_id=provider_folder_id,
            name=name,
        )

        session.add(folder)
        await session.flush()

        counters.folders_created += 1

        return folder

    if folder.name != name:
        folder.name = name
        counters.folders_updated += 1

    return folder


async def get_or_create_sync_state(
    session: AsyncSession,
    account_id: uuid.UUID,
    folder_id: uuid.UUID,
) -> SyncState:
    stmt = select(SyncState).where(
        SyncState.account_id == account_id,
        SyncState.folder_id == folder_id,
    )
    result = await session.execute(stmt)
    sync_state = result.scalar_one_or_none()

    if sync_state is not None:
        return sync_state

    sync_state = SyncState(
        account_id=account_id,
        folder_id=folder_id,
        checkpoint=None,
        last_synced_at=None,
    )

    session.add(sync_state)
    await session.flush()

    return sync_state


def normalize_recipients(recipients: list[str]) -> str:
    return ", ".join(recipients)


def message_needs_update(
    message: Message,
    subject: str | None,
    sender: str | None,
    recipients: str,
    body_text: str | None,
    sent_at: datetime | None,
    is_read: bool,
    is_starred: bool,
) -> bool:
    return any(
        [
            message.subject != subject,
            message.sender != sender,
            message.recipients != recipients,
            message.body_text != body_text,
            message.sent_at != sent_at,
            message.is_read != is_read,
            message.is_starred != is_starred,
        ]
    )


async def sync_message(
    session: AsyncSession,
    account_id: uuid.UUID,
    folder_id: uuid.UUID,
    provider_message_id: str,
    subject: str | None,
    sender: str | None,
    recipients: str,
    body_text: str | None,
    sent_at: datetime | None,
    is_read: bool,
    is_starred: bool,
    counters: SyncCounters,
) -> Message:
    stmt = select(Message).where(
        Message.account_id == account_id,
        Message.folder_id == folder_id,
        Message.provider_message_id == provider_message_id,
    )
    result = await session.execute(stmt)
    message = result.scalar_one_or_none()

    if message is None:
        message = Message(
            account_id=account_id,
            folder_id=folder_id,
            provider_message_id=provider_message_id,
            subject=subject,
            sender=sender,
            recipients=recipients,
            body_text=body_text,
            sent_at=sent_at,
            is_read=is_read,
            is_starred=is_starred,
            is_deleted=False,
        )

        session.add(message)
        await session.flush()

        counters.messages_created += 1

        return message

    if message_needs_update(
        message=message,
        subject=subject,
        sender=sender,
        recipients=recipients,
        body_text=body_text,
        sent_at=sent_at,
        is_read=is_read,
        is_starred=is_starred,
    ):
        message.subject = subject
        message.sender = sender
        message.recipients = recipients
        message.body_text = body_text
        message.sent_at = sent_at
        message.is_read = is_read
        message.is_starred = is_starred

        counters.messages_updated += 1

    return message


async def message_has_attachments(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> bool:
    stmt = select(func.count()).select_from(Attachment).where(
        Attachment.message_id == message_id,
    )
    result = await session.execute(stmt)

    return result.scalar_one() > 0


async def store_message_attachments(
    session: AsyncSession,
    message_id: uuid.UUID,
    attachments: list[ConnectorOutgoingAttachment] | None,
) -> None:
    if not attachments:
        return

    if await message_has_attachments(session, message_id):
        return

    for attachment_data in attachments:
        if not attachment_data.content:
            continue

        filename = attachment_data.filename or "attachment"
        content_type = attachment_data.content_type or "application/octet-stream"
        object_key = f"messages/{message_id}/{uuid.uuid4()}-{filename}"

        upload_file(
            object_key=object_key,
            content=attachment_data.content,
            content_type=content_type,
        )

        attachment = Attachment(
            message_id=message_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(attachment_data.content),
            object_key=object_key,
        )

        session.add(attachment)


async def sync_account(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> SyncResult | None:
    account = await get_mail_account(session, account_id)

    if account is None:
        return None

    connector = build_connector(account)
    counters = SyncCounters()

    connector_folders = await connector.list_folders()

    for connector_folder in connector_folders:
        folder = await get_or_create_folder(
            session=session,
            account_id=account.id,
            provider_folder_id=connector_folder.provider_folder_id,
            name=connector_folder.name,
            counters=counters,
        )

        sync_state = await get_or_create_sync_state(
            session=session,
            account_id=account.id,
            folder_id=folder.id,
        )

        connector_messages = await connector.list_messages(
            folder_provider_id=connector_folder.provider_folder_id,
            checkpoint=sync_state.checkpoint,
        )

        for connector_message in connector_messages:
            message = await sync_message(
                session=session,
                account_id=account.id,
                folder_id=folder.id,
                provider_message_id=connector_message.provider_message_id,
                subject=connector_message.subject,
                sender=connector_message.sender,
                recipients=normalize_recipients(connector_message.recipients),
                body_text=connector_message.body_text,
                sent_at=connector_message.sent_at,
                is_read=connector_message.is_read,
                is_starred=connector_message.is_starred,
                counters=counters,
            )

            await store_message_attachments(
                session=session,
                message_id=message.id,
                attachments=connector_message.attachments,
            )

        sync_state.last_synced_at = datetime.now(timezone.utc)

    await session.commit()

    return SyncResult(
        account_id=account.id,
        folders_created=counters.folders_created,
        folders_updated=counters.folders_updated,
        messages_created=counters.messages_created,
        messages_updated=counters.messages_updated,
    )