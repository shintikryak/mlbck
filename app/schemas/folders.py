import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FolderRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    provider_folder_id: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)