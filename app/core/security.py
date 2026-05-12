from cryptography.fernet import Fernet

from app.core.config import settings


FERNET_PREFIX = "fernet:"


def _get_fernet() -> Fernet | None:
    if not settings.secret_encryption_key:
        return None

    return Fernet(settings.secret_encryption_key.encode())


def encrypt_secret(secret: str | None) -> str | None:
    if not secret:
        return None

    if secret.startswith(FERNET_PREFIX):
        return secret

    fernet = _get_fernet()

    if fernet is None:
        return secret

    encrypted = fernet.encrypt(secret.encode()).decode()

    return f"{FERNET_PREFIX}{encrypted}"


def decrypt_secret(encrypted_secret: str | None) -> str | None:
    if not encrypted_secret:
        return None

    if not encrypted_secret.startswith(FERNET_PREFIX):
        return encrypted_secret

    fernet = _get_fernet()

    if fernet is None:
        raise RuntimeError("SECRET_ENCRYPTION_KEY is required to decrypt stored secret")

    token = encrypted_secret.removeprefix(FERNET_PREFIX)

    return fernet.decrypt(token.encode()).decode()