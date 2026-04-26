from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.users import UserCreate


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=data.email,
        hashed_password=f"dev:{data.password}",
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user