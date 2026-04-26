import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment
from app.services.messages import get_message
from app.storage.s3 import download_file, upload_file


async def create_attachment(
    session: AsyncSession,
    message_id: uuid.UUID,
    file: UploadFile,
) -> Attachment | None:
    message = await get_message(session, message_id)

    if message is None:
        return None

    content = await file.read()
    object_key = f"messages/{message_id}/{uuid.uuid4()}-{file.filename}"

    upload_file(
        object_key=object_key,
        content=content,
        content_type=file.content_type,
    )

    attachment = Attachment(
        message_id=message_id,
        filename=file.filename or "attachment",
        content_type=file.content_type,
        size_bytes=len(content),
        object_key=object_key,
    )

    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)

    return attachment


async def list_attachments(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> list[Attachment]:
    stmt = (
        select(Attachment)
        .where(Attachment.message_id == message_id)
        .order_by(Attachment.created_at.desc())
    )

    result = await session.execute(stmt)

    return list(result.scalars().all())


async def get_attachment(
    session: AsyncSession,
    attachment_id: uuid.UUID,
) -> Attachment | None:
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await session.execute(stmt)

    return result.scalar_one_or_none()


async def download_attachment(
    session: AsyncSession,
    attachment_id: uuid.UUID,
):
    attachment = await get_attachment(session, attachment_id)

    if attachment is None:
        return None, None

    s3_object = download_file(attachment.object_key)

    return attachment, s3_object