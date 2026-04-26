import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


async def list_messages(
    session: AsyncSession,
    account_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    query: str | None = None,
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.account_id == account_id)
        .where(Message.is_deleted.is_(False))
        .order_by(Message.sent_at.desc().nullslast(), Message.created_at.desc())
    )

    if folder_id is not None:
        stmt = stmt.where(Message.folder_id == folder_id)

    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Message.subject.ilike(pattern),
                Message.sender.ilike(pattern),
                Message.body_text.ilike(pattern),
            )
        )

    result = await session.execute(stmt)

    return list(result.scalars().all())


async def get_message(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> Message | None:
    stmt = select(Message).where(Message.id == message_id)
    result = await session.execute(stmt)

    return result.scalar_one_or_none()


async def set_message_read(
    session: AsyncSession,
    message_id: uuid.UUID,
    is_read: bool,
) -> Message | None:
    message = await get_message(session, message_id)

    if message is None:
        return None

    message.is_read = is_read

    await session.commit()
    await session.refresh(message)

    return message


async def set_message_starred(
    session: AsyncSession,
    message_id: uuid.UUID,
    is_starred: bool,
) -> Message | None:
    message = await get_message(session, message_id)

    if message is None:
        return None

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