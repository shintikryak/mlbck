import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mail_account import MailAccount
from app.schemas.accounts import MailAccountCreate
from app.core.security import encrypt_secret

async def create_mail_account(
    session: AsyncSession,
    data: MailAccountCreate,
) -> MailAccount:
    account = MailAccount(
        user_id=data.user_id,
        email=data.email,
        provider=data.provider,
        imap_host=data.imap_host,
        imap_port=data.imap_port,
        smtp_host=data.smtp_host,
        smtp_port=data.smtp_port,
        encrypted_secret=encrypt_secret(data.secret),
    )

    session.add(account)
    await session.commit()
    await session.refresh(account)

    return account


async def list_mail_accounts(
    session: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> list[MailAccount]:
    stmt = select(MailAccount).order_by(MailAccount.created_at.desc())

    if user_id is not None:
        stmt = stmt.where(MailAccount.user_id == user_id)

    result = await session.execute(stmt)

    return list(result.scalars().all())


async def get_mail_account(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> MailAccount | None:
    stmt = select(MailAccount).where(MailAccount.id == account_id)
    result = await session.execute(stmt)

    return result.scalar_one_or_none()