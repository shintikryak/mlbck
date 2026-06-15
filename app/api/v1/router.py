from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import accounts, attachments, folders, info, messages, send, sync, users
from app.core.database import get_session
from app.storage.s3 import check_object_storage

router = APIRouter()

router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
router.include_router(folders.router, tags=["folders"])
router.include_router(messages.router, tags=["messages"])
router.include_router(sync.router, tags=["sync"])
router.include_router(attachments.router, tags=["attachments"])
router.include_router(send.router, tags=["send"])
router.include_router(info.router, prefix="/info", tags=["info"])


@router.get(
    "/health",
    summary="Check API, database and object storage availability",
    description="Returns the current status of the API service, PostgreSQL and MinIO object storage.",
)
async def health_check(session: AsyncSession = Depends(get_session)):
    components = {
        "api": "ok",
        "database": "ok",
        "object_storage": "ok",
    }

    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        components["database"] = "error"

    try:
        check_object_storage()
    except Exception:
        components["object_storage"] = "error"

    status = "ok"

    if any(value != "ok" for value in components.values()):
        status = "degraded"

    return {
        "status": status,
        "components": components,
    }