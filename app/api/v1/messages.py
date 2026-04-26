import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.messages import MessageRead, MessageReadUpdate, MessageStarUpdate
from app.services.messages import (
    delete_message,
    get_message,
    list_messages,
    restore_message,
    set_message_read,
    set_message_starred,
)

router = APIRouter()


@router.get("/accounts/{account_id}/messages", response_model=list[MessageRead])
async def list_messages_endpoint(
    account_id: uuid.UUID,
    folder_id: uuid.UUID | None = Query(default=None),
    query: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    return await list_messages(session, account_id, folder_id, query)


@router.get("/messages/{message_id}", response_model=MessageRead)
async def get_message_endpoint(
    message_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    message = await get_message(session, message_id)

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message


@router.patch("/messages/{message_id}/read", response_model=MessageRead)
async def set_message_read_endpoint(
    message_id: uuid.UUID,
    data: MessageReadUpdate,
    session: AsyncSession = Depends(get_session),
):
    message = await set_message_read(session, message_id, data.is_read)

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message


@router.patch("/messages/{message_id}/star", response_model=MessageRead)
async def set_message_starred_endpoint(
    message_id: uuid.UUID,
    data: MessageStarUpdate,
    session: AsyncSession = Depends(get_session),
):
    message = await set_message_starred(session, message_id, data.is_starred)

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message


@router.delete("/messages/{message_id}", response_model=MessageRead)
async def delete_message_endpoint(
    message_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    message = await delete_message(session, message_id)

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message


@router.patch("/messages/{message_id}/restore", response_model=MessageRead)
async def restore_message_endpoint(
    message_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    message = await restore_message(session, message_id)

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message