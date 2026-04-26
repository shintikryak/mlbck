import asyncio
import base64
import imaplib
import re
from datetime import datetime
from email import message_from_bytes, policy
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime, parseaddr

from app.connectors.base import ConnectorFolder, ConnectorMessage


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
        client = imaplib.IMAP4_SSL(self.host, self.port)
        client.login(self.email_address, self.password)
        return client

    def _list_folders(self) -> list[ConnectorFolder]:
        client = self._connect()

        try:
            status, data = client.list()

            if status != "OK" or data is None:
                return []

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
            client.logout()

    def _list_messages(self, folder_provider_id: str) -> list[ConnectorMessage]:
        client = self._connect()

        try:
            if not self._select_folder(client, folder_provider_id):
                return []

            status, data = client.uid("search", None, "ALL")

            if status != "OK" or not data or not data[0]:
                return []

            uids = data[0].split()
            selected_uids = uids[-self.fetch_limit :]

            messages = []

            for uid in selected_uids:
                status, fetch_data = client.uid("fetch", uid, "(RFC822 FLAGS)")

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
                    )
                )

            return messages
        finally:
            client.logout()

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