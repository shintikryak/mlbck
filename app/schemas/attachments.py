import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentRead(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    filename: str
    content_type: str | None
    size_bytes: int
    object_key: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)