import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.sync import SyncResult
from app.services.sync import MissingCredentialsError, UnsupportedProviderError, sync_account

router = APIRouter()


@router.post("/accounts/{account_id}/sync", response_model=SyncResult)
async def sync_account_endpoint(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await sync_account(session, account_id)
    except UnsupportedProviderError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only fake and imap providers are supported at this stage",
        )
    except MissingCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IMAP password or app password is required",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mail account not found",
        )

    return result