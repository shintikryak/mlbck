import uuid

from pydantic import BaseModel


class SyncResult(BaseModel):
    account_id: uuid.UUID
    folders_created: int
    folders_updated: int
    messages_created: int
    messages_updated: int