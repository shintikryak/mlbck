"""add indexes

Revision ID: b01ce29fc40a
Revises: 63870fcb7c59
Create Date: 2026-05-11 17:09:25.228073
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b01ce29fc40a'
down_revision: str | None = '63870fcb7c59'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_email "
        "ON users (email)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mail_accounts_user_id "
        "ON mail_accounts (user_id)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mail_accounts_user_email "
        "ON mail_accounts (user_id, email)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_folders_account_id "
        "ON folders (account_id)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_folders_account_provider_folder "
        "ON folders (account_id, provider_folder_id)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_account_deleted_sent "
        "ON messages (account_id, is_deleted, sent_at DESC)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_folder_id "
        "ON messages (folder_id)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_provider_message "
        "ON messages (account_id, folder_id, provider_message_id)"
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_messages_search_vector
        ON messages
        USING GIN (
            to_tsvector(
                'simple',
                coalesce(subject, '') || ' ' ||
                coalesce(sender, '') || ' ' ||
                coalesce(recipients, '') || ' ' ||
                coalesce(body_text, '')
            )
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_attachments_message_id "
        "ON attachments (message_id)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sync_states_account_folder "
        "ON sync_states (account_id, folder_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sync_states_account_folder")
    op.execute("DROP INDEX IF EXISTS ix_attachments_message_id")
    op.execute("DROP INDEX IF EXISTS ix_messages_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_messages_provider_message")
    op.execute("DROP INDEX IF EXISTS ix_messages_folder_id")
    op.execute("DROP INDEX IF EXISTS ix_messages_account_deleted_sent")
    op.execute("DROP INDEX IF EXISTS ix_folders_account_provider_folder")
    op.execute("DROP INDEX IF EXISTS ix_folders_account_id")
    op.execute("DROP INDEX IF EXISTS ix_mail_accounts_user_email")
    op.execute("DROP INDEX IF EXISTS ix_mail_accounts_user_id")
    op.execute("DROP INDEX IF EXISTS ix_users_email")