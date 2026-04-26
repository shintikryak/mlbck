import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MailAccountCreate(BaseModel):
    user_id: uuid.UUID
    email: str
    provider: str
    imap_host: str
    imap_port: int = 993
    smtp_host: str
    smtp_port: int = 587
    secret: str | None = None


class MailAccountRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    provider: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)