from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    recipients: list[str] = Field(min_length=1)
    subject: str
    body_text: str