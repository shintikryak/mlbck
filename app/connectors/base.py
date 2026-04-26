from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ConnectorFolder:
    provider_folder_id: str
    name: str


@dataclass(frozen=True)
class ConnectorMessage:
    provider_message_id: str
    folder_provider_id: str
    subject: str | None
    sender: str | None
    recipients: list[str]
    body_text: str | None
    sent_at: datetime | None
    is_read: bool = False
    is_starred: bool = False


@dataclass(frozen=True)
class ConnectorSendResult:
    provider_message_id: str
    sent_at: datetime


class MailboxConnector(Protocol):
    async def list_folders(self) -> list[ConnectorFolder]:
        ...

    async def list_messages(
        self,
        folder_provider_id: str,
        checkpoint: str | None = None,
    ) -> list[ConnectorMessage]:
        ...

    async def send_message(
        self,
        recipients: list[str],
        subject: str,
        body_text: str,
    ) -> ConnectorSendResult:
        ...