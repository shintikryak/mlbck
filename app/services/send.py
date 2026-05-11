import uuid

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorOutgoingAttachment
from app.connectors.fake_connector import FakeMailboxConnector
from app.connectors.smtp_connector import SmtpMailboxConnector
from app.models.attachment import Attachment
from app.models.folder import Folder
from app.models.message import Message
from app.services.accounts import get_mail_account
from app.services.sync import MissingCredentialsError, UnsupportedProviderError
from app.storage.s3 import upload_file


async def get_or_create_sent_folder(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> Folder:
    stmt = (
        select(Folder)
        .where(Folder.account_id == account_id)
        .where(Folder.provider_folder_id.in_(["SENT", "Sent", "sent"]))
        .order_by(Folder.created_at.asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    folder = result.scalars().first()

    if folder is not None:
        return folder

    stmt = (
        select(Folder)
        .where(Folder.account_id == account_id)
        .where(func.lower(Folder.name) == "sent")
        .order_by(Folder.created_at.asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    folder = result.scalars().first()

    if folder is not None:
        return folder

    folder = Folder(
        account_id=account_id,
        provider_folder_id="SENT",
        name="Sent",
    )

    session.add(folder)
    await session.flush()

    return folder


def build_send_connector(account):
    if account.provider == "fake":
        return FakeMailboxConnector(account.email)

    if account.provider == "imap":
        if not account.encrypted_secret:
            raise MissingCredentialsError

        return SmtpMailboxConnector(
            email_address=account.email,
            password=account.encrypted_secret,
            host=account.smtp_host,
            port=account.smtp_port,
        )

    raise UnsupportedProviderError


async def read_upload_file(file: UploadFile | None) -> ConnectorOutgoingAttachment | None:
    if file is None:
        return None

    if not file.filename:
        return None

    content = await file.read()

    if not content:
        return None

    return ConnectorOutgoingAttachment(
        filename=file.filename,
        content=content,
        content_type=file.content_type or "application/octet-stream",
    )


async def send_message(
    session: AsyncSession,
    account_id: uuid.UUID,
    recipients: list[str],
    subject: str,
    body_text: str,
    file: UploadFile | None = None,
) -> Message | None:
    account = await get_mail_account(session, account_id)

    if account is None:
        return None

    sent_folder = await get_or_create_sent_folder(session, account.id)
    connector = build_send_connector(account)

    attachment_data = await read_upload_file(file)
    outgoing_attachments = []

    if attachment_data is not None:
        outgoing_attachments.append(attachment_data)

    send_result = await connector.send_message(
        recipients=recipients,
        subject=subject,
        body_text=body_text,
        attachments=outgoing_attachments,
    )

    message = Message(
        account_id=account.id,
        folder_id=sent_folder.id,
        provider_message_id=send_result.provider_message_id,
        subject=subject,
        sender=account.email,
        recipients=", ".join(recipients),
        body_text=body_text,
        sent_at=send_result.sent_at,
        is_read=True,
        is_starred=False,
        is_deleted=False,
    )

    session.add(message)
    await session.flush()

    for attachment in outgoing_attachments:
        object_key = f"messages/{message.id}/{uuid.uuid4()}-{attachment.filename}"

        upload_file(
            object_key=object_key,
            content=attachment.content,
            content_type=attachment.content_type,
        )

        session.add(
            Attachment(
                message_id=message.id,
                filename=attachment.filename,
                content_type=attachment.content_type,
                size_bytes=len(attachment.content),
                object_key=object_key,
            )
        )

    await session.commit()
    await session.refresh(message)

    return message