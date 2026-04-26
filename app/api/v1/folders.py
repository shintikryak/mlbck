import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.folders import FolderRead
from app.services.folders import list_folders

router = APIRouter()


@router.get("/accounts/{account_id}/folders", response_model=list[FolderRead])
async def list_folders_endpoint(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    return await list_folders(session, account_id)