import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder


async def list_folders(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> list[Folder]:
    stmt = (
        select(Folder)
        .where(Folder.account_id == account_id)
        .order_by(Folder.name)
    )

    result = await session.execute(stmt)

    return list(result.scalars().all())