import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.messages import MessageRead
from app.schemas.send import SendMessageRequest
from app.services.send import send_message
from app.services.sync import UnsupportedProviderError

router = APIRouter()


@router.post("/accounts/{account_id}/send", response_model=MessageRead)
async def send_message_endpoint(
    account_id: uuid.UUID,
    data: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        message = await send_message(session, account_id, data)
    except UnsupportedProviderError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only fake provider is supported at this stage",
        )

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mail account not found",
        )

    return message