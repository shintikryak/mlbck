import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.fake_connector import FakeMailboxConnector
from app.models.folder import Folder
from app.models.message import Message
from app.schemas.send import SendMessageRequest
from app.services.accounts import get_mail_account
from app.services.sync import UnsupportedProviderError


async def get_or_create_sent_folder(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> Folder:
    stmt = select(Folder).where(
        Folder.account_id == account_id,
        Folder.provider_folder_id == "SENT",
    )
    result = await session.execute(stmt)
    folder = result.scalar_one_or_none()

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


async def send_message(
    session: AsyncSession,
    account_id: uuid.UUID,
    data: SendMessageRequest,
) -> Message | None:
    account = await get_mail_account(session, account_id)

    if account is None:
        return None

    if account.provider != "fake":
        raise UnsupportedProviderError

    connector = FakeMailboxConnector(account.email)

    send_result = await connector.send_message(
        recipients=data.recipients,
        subject=data.subject,
        body_text=data.body_text,
    )

    sent_folder = await get_or_create_sent_folder(session, account.id)

    message = Message(
        account_id=account.id,
        folder_id=sent_folder.id,
        provider_message_id=send_result.provider_message_id,
        subject=data.subject,
        sender=account.email,
        recipients=", ".join(data.recipients),
        body_text=data.body_text,
        sent_at=send_result.sent_at,
        is_read=True,
        is_starred=False,
        is_deleted=False,
    )

    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message