import asyncio
import base64
import imaplib
import re
import socket
import ssl
from datetime import datetime
from email import message_from_bytes, policy
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime, parseaddr

from app.connectors.base import (
    ConnectorFolder,
    ConnectorMessage,
    ConnectorOutgoingAttachment,
)
from app.connectors.errors import (
    MailProviderAuthError,
    MailProviderConnectionError,
    MailProviderMailboxError,
    MailProviderTimeoutError,
)


class ImapMailboxConnector:
    def __init__(
        self,
        email_address: str,
        password: str,
        host: str,
        port: int = 993,
        fetch_limit: int = 25,
    ) -> None:
        self.email_address = email_address
        self.password = password
        self.host = host
        self.port = port
        self.fetch_limit = fetch_limit

    async def list_folders(self) -> list[ConnectorFolder]:
        return await asyncio.to_thread(self._list_folders)

    async def list_messages(
        self,
        folder_provider_id: str,
        checkpoint: str | None = None,
    ) -> list[ConnectorMessage]:
        return await asyncio.to_thread(self._list_messages, folder_provider_id)

    def _connect(self) -> imaplib.IMAP4_SSL:
        try:
            client = imaplib.IMAP4_SSL(self.host, self.port)
        except (socket.timeout, TimeoutError) as exc:
            raise MailProviderTimeoutError("IMAP connection timed out") from exc
        except (socket.gaierror, ConnectionRefusedError, OSError, ssl.SSLError) as exc:
            raise MailProviderConnectionError("Could not connect to IMAP provider") from exc

        try:
            client.login(self.email_address, self.password)
        except imaplib.IMAP4.error as exc:
            self._safe_logout(client)

            error_text = str(exc).lower()

            if (
                "authenticationfailed" in error_text
                or "invalid credentials" in error_text
                or "imap is disabled" in error_text
                or "login" in error_text
            ):
                raise MailProviderAuthError("Invalid IMAP credentials or IMAP is disabled") from exc

            raise MailProviderConnectionError("IMAP login failed") from exc
        except (socket.timeout, TimeoutError) as exc:
            self._safe_logout(client)
            raise MailProviderTimeoutError("IMAP login timed out") from exc
        except (OSError, ssl.SSLError) as exc:
            self._safe_logout(client)
            raise MailProviderConnectionError("IMAP login connection error") from exc

        return client

    def _list_folders(self) -> list[ConnectorFolder]:
        client = self._connect()

        try:
            try:
                status, data = client.list()
            except (socket.timeout, TimeoutError) as exc:
                raise MailProviderTimeoutError("IMAP folder listing timed out") from exc
            except imaplib.IMAP4.error as exc:
                raise MailProviderMailboxError("IMAP folder listing failed") from exc
            except OSError as exc:
                raise MailProviderConnectionError("IMAP folder listing connection error") from exc

            if status != "OK" or data is None:
                raise MailProviderMailboxError("IMAP provider returned invalid folder list")

            folders = []

            for raw_line in data:
                if raw_line is None:
                    continue

                line = raw_line.decode(errors="ignore")

                if "\\Noselect" in line:
                    continue

                provider_folder_id = self._extract_folder_name(line)

                if provider_folder_id:
                    folders.append(
                        ConnectorFolder(
                            provider_folder_id=provider_folder_id,
                            name=self._decode_modified_utf7(provider_folder_id),
                        )
                    )

            return folders
        finally:
            self._safe_logout(client)

    def _list_messages(self, folder_provider_id: str) -> list[ConnectorMessage]:
        client = self._connect()

        try:
            if not self._select_folder(client, folder_provider_id):
                return []

            try:
                status, data = client.uid("search", None, "ALL")
            except (socket.timeout, TimeoutError) as exc:
                raise MailProviderTimeoutError("IMAP message search timed out") from exc
            except imaplib.IMAP4.error as exc:
                raise MailProviderMailboxError("IMAP message search failed") from exc
            except OSError as exc:
                raise MailProviderConnectionError("IMAP message search connection error") from exc

            if status != "OK" or not data or not data[0]:
                return []

            uids = data[0].split()
            selected_uids = uids[-self.fetch_limit :]

            messages = []

            for uid in selected_uids:
                try:
                    status, fetch_data = client.uid("fetch", uid, "(RFC822 FLAGS)")
                except (socket.timeout, TimeoutError) as exc:
                    raise MailProviderTimeoutError("IMAP message fetch timed out") from exc
                except imaplib.IMAP4.error:
                    continue
                except OSError as exc:
                    raise MailProviderConnectionError("IMAP message fetch connection error") from exc

                if status != "OK" or not fetch_data:
                    continue

                raw_message = None
                flags_raw = b""

                for item in fetch_data:
                    if isinstance(item, tuple):
                        flags_raw += item[0]
                        raw_message = item[1]
                    elif isinstance(item, bytes):
                        flags_raw += item

                if raw_message is None:
                    continue

                try:
                    parsed = message_from_bytes(raw_message, policy=policy.default)
                    flags_text = flags_raw.decode(errors="ignore")

                    messages.append(
                        ConnectorMessage(
                            provider_message_id=uid.decode(errors="ignore"),
                            folder_provider_id=folder_provider_id,
                            subject=self._decode_mime_header(parsed.get("Subject")),
                            sender=self._extract_sender(parsed),
                            recipients=self._extract_recipients(parsed),
                            body_text=self._extract_body_text(parsed),
                            sent_at=self._extract_sent_at(parsed),
                            is_read="\\Seen" in flags_text,
                            is_starred="\\Flagged" in flags_text,
                            attachments=self._extract_attachments(parsed),
                        )
                    )
                except Exception:
                    continue

            return messages
        finally:
            self._safe_logout(client)

    def _select_folder(self, client: imaplib.IMAP4_SSL, folder_provider_id: str) -> bool:
        variants = [
            folder_provider_id,
            self._quote_folder_name(folder_provider_id),
        ]

        for variant in variants:
            try:
                status, _ = client.select(variant, readonly=True)

                if status == "OK":
                    return True
            except imaplib.IMAP4.error:
                continue
            except (socket.timeout, TimeoutError) as exc:
                raise MailProviderTimeoutError("IMAP folder select timed out") from exc
            except OSError as exc:
                raise MailProviderConnectionError("IMAP folder select connection error") from exc

        return False

    def _quote_folder_name(self, folder_name: str) -> str:
        escaped = folder_name.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _extract_folder_name(self, line: str) -> str | None:
        closing_flags_index = line.find(")")

        if closing_flags_index == -1:
            return None

        tail = line[closing_flags_index + 1 :].strip()

        if not tail:
            return None

        tail = self._skip_imap_token(tail)

        if not tail:
            return None

        if tail.startswith('"'):
            return self._read_quoted_value(tail)

        return tail.split()[0].strip()

    def _skip_imap_token(self, value: str) -> str:
        value = value.strip()

        if not value:
            return ""

        if value.startswith('"'):
            end_index = 1

            while end_index < len(value):
                if value[end_index] == '"' and value[end_index - 1] != "\\":
                    return value[end_index + 1 :].strip()

                end_index += 1

            return ""

        parts = value.split(maxsplit=1)

        if len(parts) == 1:
            return ""

        return parts[1].strip()

    def _read_quoted_value(self, value: str) -> str | None:
        result = []
        index = 1

        while index < len(value):
            char = value[index]

            if char == '"' and value[index - 1] != "\\":
                return "".join(result)

            result.append(char)
            index += 1

        return None

    def _decode_modified_utf7(self, value: str) -> str:
        def replace_match(match: re.Match) -> str:
            chunk = match.group(1)

            if chunk == "":
                return "&"

            chunk = chunk.replace(",", "/")
            chunk += "=" * (-len(chunk) % 4)

            try:
                return base64.b64decode(chunk).decode("utf-16-be")
            except Exception:
                return match.group(0)

        return re.sub(r"&([^-]*)-", replace_match, value)

    def _decode_mime_header(self, value: str | None) -> str | None:
        if value is None:
            return None

        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    def _extract_sender(self, message: Message) -> str | None:
        raw_sender = message.get("From")

        if raw_sender is None:
            return None

        name, address = parseaddr(str(raw_sender))

        return address or name or str(raw_sender)

    def _extract_recipients(self, message: Message) -> list[str]:
        raw_values = []

        for header in ("To", "Cc", "Bcc"):
            value = message.get(header)

            if value:
                raw_values.append(str(value))

        addresses = []

        for name, address in getaddresses(raw_values):
            addresses.append(address or name)

        return addresses

    def _extract_sent_at(self, message: Message) -> datetime | None:
        raw_date = message.get("Date")

        if raw_date is None:
            return None

        try:
            return parsedate_to_datetime(str(raw_date))
        except Exception:
            return None

    def _extract_body_text(self, message: Message) -> str | None:
        if message.is_multipart():
            html_fallback = None

            for part in message.walk():
                content_disposition = part.get_content_disposition()
                content_type = part.get_content_type()

                if content_disposition == "attachment":
                    continue

                if content_type == "text/plain":
                    return self._safe_get_content(part)

                if content_type == "text/html" and html_fallback is None:
                    html_fallback = self._safe_get_content(part)

            if html_fallback:
                return self._strip_html(html_fallback)

            return None

        content_type = message.get_content_type()
        content = self._safe_get_content(message)

        if content_type == "text/html" and content is not None:
            return self._strip_html(content)

        return content
    
    def _extract_attachments(self, message: Message) -> list[ConnectorOutgoingAttachment]:
        if not message.is_multipart():
            return []

        attachments = []

        for part in message.walk():
            content_disposition = part.get_content_disposition()
            filename = part.get_filename()

            if content_disposition != "attachment" and not filename:
                continue

            payload = part.get_payload(decode=True)

            if not payload:
                continue

            decoded_filename = self._decode_attachment_filename(filename)

            attachments.append(
                ConnectorOutgoingAttachment(
                    filename=decoded_filename,
                    content=payload,
                    content_type=part.get_content_type() or "application/octet-stream",
                )
            )

        return attachments


    def _decode_attachment_filename(self, filename: str | None) -> str:
        if not filename:
            return "attachment"

        decoded = self._decode_mime_header(filename)

        if not decoded:
            return "attachment"

        return decoded

    def _safe_get_content(self, message: Message) -> str | None:
        try:
            content = message.get_content()
        except Exception:
            payload = message.get_payload(decode=True)

            if payload is None:
                return None

            charset = message.get_content_charset() or "utf-8"

            try:
                return payload.decode(charset, errors="replace")
            except Exception:
                return payload.decode("utf-8", errors="replace")

        if isinstance(content, str):
            return content

        return str(content)

    def _strip_html(self, value: str) -> str:
        return re.sub(r"<[^>]+>", " ", value).strip()

    def _safe_logout(self, client: imaplib.IMAP4_SSL) -> None:
        try:
            client.logout()
        except Exception:
            pass