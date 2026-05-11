import uuid
from datetime import datetime, timezone

from app.connectors.base import (
    ConnectorFolder,
    ConnectorMessage,
    ConnectorOutgoingAttachment,
    ConnectorSendResult,
)


class FakeMailboxConnector:
    def __init__(self, email: str) -> None:
        self.email = email

    async def list_folders(self) -> list[ConnectorFolder]:
        return [
            ConnectorFolder(provider_folder_id="INBOX", name="Inbox"),
            ConnectorFolder(provider_folder_id="SENT", name="Sent"),
        ]

    async def list_messages(
        self,
        folder_provider_id: str,
        checkpoint: str | None = None,
    ) -> list[ConnectorMessage]:
        messages = {
            "INBOX": [
                ConnectorMessage(
                    provider_message_id="fake-inbox-1",
                    folder_provider_id="INBOX",
                    subject="Welcome to Mailback",
                    sender="support@mailback.local",
                    recipients=[self.email],
                    body_text="This is the first synchronized email message.",
                    sent_at=datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
                    is_read=False,
                    is_starred=True,
                ),
                ConnectorMessage(
                    provider_message_id="fake-inbox-2",
                    folder_provider_id="INBOX",
                    subject="Project status update",
                    sender="team@example.com",
                    recipients=[self.email],
                    body_text="The mailbox synchronization module is ready for testing.",
                    sent_at=datetime(2026, 4, 25, 11, 30, tzinfo=timezone.utc),
                    is_read=True,
                    is_starred=False,
                ),
            ],
            "SENT": [
                ConnectorMessage(
                    provider_message_id="fake-sent-1",
                    folder_provider_id="SENT",
                    subject="Re: Project status update",
                    sender=self.email,
                    recipients=["team@example.com"],
                    body_text="Thank you, I will check the synchronization results.",
                    sent_at=datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
                    is_read=True,
                    is_starred=False,
                ),
            ],
        }

        return messages.get(folder_provider_id, [])

    async def send_message(
        self,
        recipients: list[str],
        subject: str,
        body_text: str,
        attachments: list[ConnectorOutgoingAttachment] | None = None,
    ) -> ConnectorSendResult:
        return ConnectorSendResult(
            provider_message_id=f"fake-sent-{uuid.uuid4()}",
            sent_at=datetime.now(timezone.utc),
        )