from fastapi import APIRouter

from app.api.v1 import accounts, attachments, folders, messages, send, sync, users

router = APIRouter()

router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
router.include_router(folders.router, tags=["folders"])
router.include_router(messages.router, tags=["messages"])
router.include_router(sync.router, tags=["sync"])
router.include_router(attachments.router, tags=["attachments"])
router.include_router(send.router, tags=["send"])


@router.get("/health")
async def health_check():
    return {"status": "ok"}