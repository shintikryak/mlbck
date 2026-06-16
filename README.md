# mlbck
## Demo and Verification Scenario

This section describes a minimal scenario for checking the Mailback MVP locally.

### 1. Start the project

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
```

Swagger UI will be available at:

```text
http://localhost:8000/docs
```

### 2. Check service health

Open Swagger UI and run:

```text
GET /api/v1/health
GET /api/v1/info
```

Expected result: the API returns service status and basic project information.

### 3. Create a local user

Run:

```text
POST /api/v1/users
```

Example body:

```json
{
  "email": "demo@mailback.local",
  "password": "123456"
}
```

Save the returned `user_id`.

### 4. Connect a mailbox account

Run:

```text
POST /api/v1/accounts
```

Example body for Yandex Mail:

```json
{
  "user_id": "paste-user-id-here",
  "email": "your-test-mailbox@yandex.ru",
  "provider": "imap",
  "imap_host": "imap.yandex.ru",
  "imap_port": 993,
  "smtp_host": "smtp.yandex.ru",
  "smtp_port": 465,
  "secret": "application-password"
}
```

The response must not contain `secret` or `encrypted_secret`.

### 5. Synchronize mailbox data

Run:

```text
POST /api/v1/accounts/{account_id}/sync
```

The endpoint synchronizes folders, messages and incoming attachments from the connected mailbox.

To verify idempotency, run the same sync request again. If no new messages appeared in the mailbox, the second response should not create duplicate messages.

### 6. List and inspect messages

Run:

```text
GET /api/v1/accounts/{account_id}/messages
GET /api/v1/messages/{message_id}
```

The response should contain message metadata, subject, sender, recipients, body text and flags.

### 7. Check search

Run:

```text
GET /api/v1/accounts/{account_id}/messages?query=mailback
```

The endpoint searches through stored message fields such as subject, sender, recipients and body text.

### 8. Check read/star actions

Run:

```text
PATCH /api/v1/messages/{message_id}/read
```

Body:

```json
{
  "is_read": true
}
```

Then run:

```text
PATCH /api/v1/messages/{message_id}/star
```

Body:

```json
{
  "is_starred": true
}
```

For IMAP accounts, these actions are propagated to the mail provider through IMAP flags. After that, run synchronization again and check that the flags are not reverted.

### 9. Check attachments

For a message with attachments, run:

```text
GET /api/v1/messages/{message_id}/attachments
GET /api/v1/attachments/{attachment_id}/download
```

The file should be downloaded through the API. Attachment metadata is stored in PostgreSQL, while the binary file is stored in MinIO.

### 10. Send an email

Run:

```text
POST /api/v1/accounts/{account_id}/send
```

The endpoint sends an email through SMTP. It also supports an optional file attachment using `multipart/form-data`.

### 11. Run tests

```bash
docker compose exec api pytest -q
```

The tests verify key API and integration scenarios.

### Notes

Use `.env.example` as a template.

The `SECRET_ENCRYPTION_KEY` value must be generated locally and stored only in `.env`.

Example generation command:

```bash
docker compose exec api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
