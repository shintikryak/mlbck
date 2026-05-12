import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.errors import (
    MailProviderAuthError,
    MailProviderConnectionError,
    MailProviderSendError,
    MailProviderTimeoutError,
)
from app.core.database import get_session
from app.schemas.messages import MessageRead
from app.services.send import send_message
from app.services.sync import MissingCredentialsError, UnsupportedProviderError

router = APIRouter()


@router.post("/accounts/{account_id}/send", response_model=MessageRead)
async def send_message_endpoint(
    account_id: uuid.UUID,
    recipients: str = Form(...),
    subject: str = Form(...),
    body_text: str = Form(...),
    file: UploadFile | None = File(default=None),
    session: AsyncSession = Depends(get_session),
):
    recipient_list = [
        recipient.strip()
        for recipient in recipients.split(",")
        if recipient.strip()
    ]

    if not recipient_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one recipient is required",
        )

    try:
        message = await send_message(
            session=session,
            account_id=account_id,
            recipients=recipient_list,
            subject=subject,
            body_text=body_text,
            file=file,
        )
    except MissingCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP password or app password is required",
        )
    except UnsupportedProviderError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only fake and imap providers are supported at this stage",
        )
    except MailProviderAuthError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid SMTP credentials",
        )
    except MailProviderSendError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP provider rejected the message or recipients",
        )
    except MailProviderTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Mail provider timeout during sending",
        )
    except MailProviderConnectionError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Mail provider is unavailable during sending",
        )

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mail account not found",
        )

    return message