import asyncio
import mimetypes
import smtplib
import socket
import ssl
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

from app.connectors.base import ConnectorOutgoingAttachment, ConnectorSendResult
from app.connectors.errors import (
    MailProviderAuthError,
    MailProviderConnectionError,
    MailProviderSendError,
    MailProviderTimeoutError,
)


class SmtpMailboxConnector:
    def __init__(
        self,
        email_address: str,
        password: str,
        host: str,
        port: int = 465,
    ) -> None:
        self.email_address = email_address
        self.password = password
        self.host = host
        self.port = port

    async def send_message(
        self,
        recipients: list[str],
        subject: str,
        body_text: str,
        attachments: list[ConnectorOutgoingAttachment] | None = None,
    ) -> ConnectorSendResult:
        return await asyncio.to_thread(
            self._send_message,
            recipients,
            subject,
            body_text,
            attachments or [],
        )

    def _send_message(
        self,
        recipients: list[str],
        subject: str,
        body_text: str,
        attachments: list[ConnectorOutgoingAttachment],
    ) -> ConnectorSendResult:
        message = EmailMessage()
        message["From"] = self.email_address
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body_text)

        for attachment in attachments:
            content_type = attachment.content_type

            if not content_type or content_type == "application/octet-stream":
                guessed_type, _ = mimetypes.guess_type(attachment.filename)
                content_type = guessed_type or "application/octet-stream"

            maintype, subtype = content_type.split("/", 1)

            message.add_attachment(
                attachment.content,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
            )

        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as client:
                    client.login(self.email_address, self.password)
                    client.send_message(message)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=30) as client:
                    client.starttls()
                    client.login(self.email_address, self.password)
                    client.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            raise MailProviderAuthError("Invalid SMTP credentials") from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise MailProviderSendError("SMTP provider rejected all recipients") from exc
        except (smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
            raise MailProviderSendError("SMTP provider rejected the message") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise MailProviderTimeoutError("SMTP provider timed out") from exc
        except (
            socket.gaierror,
            ConnectionRefusedError,
            smtplib.SMTPConnectError,
            smtplib.SMTPServerDisconnected,
            OSError,
            ssl.SSLError,
        ) as exc:
            raise MailProviderConnectionError("Could not connect to SMTP provider") from exc

        return ConnectorSendResult(
            provider_message_id=f"smtp-sent-{uuid.uuid4()}",
            sent_at=datetime.now(timezone.utc),
        )