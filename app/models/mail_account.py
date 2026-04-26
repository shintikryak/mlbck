import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MailAccount(Base, TimestampMixin):
    __tablename__ = "mail_accounts"

    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_mail_accounts_user_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)

    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(nullable=False, default=993)

    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(nullable=False, default=587)

    encrypted_secret: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    user = relationship("User", back_populates="mail_accounts")
    folders = relationship(
        "Folder",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "Message",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    sync_states = relationship(
        "SyncState",
        back_populates="account",
        cascade="all, delete-orphan",
    )