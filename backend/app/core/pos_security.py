import hashlib
import hmac
import re
import secrets

from app.core.errors import ValidationFailed

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


def normalize_pos_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValidationFailed(
            "POS username must be 3-64 chars and use only letters, digits, dot, dash, "
            "or underscore."
        )
    return username


def hash_pos_password(password: str, *, salt_hex: str | None = None) -> tuple[str, str]:
    if len(password) < 4:
        raise ValidationFailed("POS password must be at least 4 characters long.")
    salt = secrets.token_bytes(16) if salt_hex is None else bytes.fromhex(salt_hex)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=64,
    )
    return salt.hex(), password_hash.hex()


def verify_pos_password(*, password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    _, computed_hash_hex = hash_pos_password(password, salt_hex=salt_hex)
    return hmac.compare_digest(computed_hash_hex, expected_hash_hex)


def issue_pos_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_pos_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
