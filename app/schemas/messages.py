import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    folder_id: uuid.UUID
    provider_message_id: str
    subject: str | None
    sender: str | None
    recipients: str | None
    body_text: str | None
    sent_at: datetime | None
    is_read: bool
    is_starred: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageReadUpdate(BaseModel):
    is_read: bool


class MessageStarUpdate(BaseModel):
    is_starred: bool