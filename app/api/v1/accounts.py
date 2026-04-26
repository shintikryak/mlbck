import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.accounts import MailAccountCreate, MailAccountRead
from app.services.accounts import create_mail_account, get_mail_account, list_mail_accounts

router = APIRouter()


@router.post("", response_model=MailAccountRead, status_code=status.HTTP_201_CREATED)
async def create_mail_account_endpoint(
    data: MailAccountCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await create_mail_account(session, data)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mail account already exists or user does not exist",
        )


@router.get("", response_model=list[MailAccountRead])
async def list_mail_accounts_endpoint(
    user_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    return await list_mail_accounts(session, user_id)


@router.get("/{account_id}", response_model=MailAccountRead)
async def get_mail_account_endpoint(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    account = await get_mail_account(session, account_id)

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mail account not found",
        )

    return account