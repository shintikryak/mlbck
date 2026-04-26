import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.attachments import AttachmentRead
from app.services.attachments import (
    create_attachment,
    download_attachment,
    list_attachments,
)

router = APIRouter()


@router.post(
    "/messages/{message_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_attachment_endpoint(
    message_id: uuid.UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    attachment = await create_attachment(session, message_id, file)

    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return attachment


@router.get(
    "/messages/{message_id}/attachments",
    response_model=list[AttachmentRead],
)
async def list_attachments_endpoint(
    message_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    return await list_attachments(session, message_id)


@router.get("/attachments/{attachment_id}/download")
async def download_attachment_endpoint(
    attachment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    attachment, s3_object = await download_attachment(session, attachment_id)

    if attachment is None or s3_object is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    encoded_filename = quote(attachment.filename)

    return StreamingResponse(
        s3_object["Body"].iter_chunks(),
        media_type=attachment.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )