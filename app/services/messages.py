import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.message import Message
from app.connectors.imap_connector import ImapMailboxConnector
from app.core.security import decrypt_secret


def build_search_condition(query: str):
    search_document = func.to_tsvector(
        "simple",
        func.concat_ws(
            " ",
            func.coalesce(Message.subject, ""),
            func.coalesce(Message.sender, ""),
            func.coalesce(Message.recipients, ""),
            func.coalesce(Message.body_text, ""),
        ),
    )

    search_query = func.websearch_to_tsquery("simple", query)

    pattern = f"%{query}%"

    return or_(
        search_document.op("@@")(search_query),
        Message.subject.ilike(pattern),
        Message.sender.ilike(pattern),
        Message.recipients.ilike(pattern),
        Message.body_text.ilike(pattern),
    )


def build_messages_filters(
    account_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    query: str | None = None,
):
    filters = [
        Message.account_id == account_id,
        Message.is_deleted.is_(False),
    ]

    if folder_id is not None:
        filters.append(Message.folder_id == folder_id)

    if query:
        filters.append(build_search_condition(query))

    return filters


async def list_messages(
    session: AsyncSession,
    account_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Message], int]:
    filters = build_messages_filters(account_id, folder_id, query)

    total_stmt = select(func.count()).select_from(Message).where(*filters)
    total_result = await session.execute(total_stmt)
    total = total_result.scalar_one()

    stmt = (
        select(Message)
        .where(*filters)
        .order_by(Message.sent_at.desc().nullslast(), Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)

    return list(result.scalars().all()), total


async def get_message(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> Message | None:
    stmt = select(Message).where(Message.id == message_id)
    result = await session.execute(stmt)

    return result.scalar_one_or_none()

async def get_message_with_provider_data(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> Message | None:
    stmt = (
        select(Message)
        .options(
            selectinload(Message.account),
            selectinload(Message.folder),
        )
        .where(Message.id == message_id)
    )
    result = await session.execute(stmt)

    return result.scalar_one_or_none()


def build_imap_connector_for_message(message: Message) -> ImapMailboxConnector | None:
    if message.account.provider != "imap":
        return None

    secret = decrypt_secret(message.account.encrypted_secret)

    if not secret:
        return None

    return ImapMailboxConnector(
        email_address=message.account.email,
        password=secret,
        host=message.account.imap_host,
        port=message.account.imap_port,
    )


async def update_provider_read_flag(message: Message, is_read: bool) -> None:
    connector = build_imap_connector_for_message(message)

    if connector is None:
        return

    await connector.set_message_read(
        folder_provider_id=message.folder.provider_folder_id,
        provider_message_id=message.provider_message_id,
        is_read=is_read,
    )


async def update_provider_starred_flag(message: Message, is_starred: bool) -> None:
    connector = build_imap_connector_for_message(message)

    if connector is None:
        return

    await connector.set_message_starred(
        folder_provider_id=message.folder.provider_folder_id,
        provider_message_id=message.provider_message_id,
        is_starred=is_starred,
    )

async def set_message_read(
    session: AsyncSession,
    message_id: uuid.UUID,
    is_read: bool,
) -> Message | None:
    message = await get_message_with_provider_data(session, message_id)

    if message is None:
        return None

    await update_provider_read_flag(message, is_read)

    message.is_read = is_read

    await session.commit()
    await session.refresh(message)

    return message


async def set_message_starred(
    session: AsyncSession,
    message_id: uuid.UUID,
    is_starred: bool,
) -> Message | None:
    message = await get_message_with_provider_data(session, message_id)

    if message is None:
        return None

    await update_provider_starred_flag(message, is_starred)

    message.is_starred = is_starred

    await session.commit()
    await session.refresh(message)

    return message


async def delete_message(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> Message | None:
    message = await get_message(session, message_id)

    if message is None:
        return None

    message.is_deleted = True

    await session.commit()
    await session.refresh(message)

    return message


async def restore_message(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> Message | None:
    message = await get_message(session, message_id)

    if message is None:
        return None

    message.is_deleted = False

    await session.commit()
    await session.refresh(message)

    return message