from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core import auth as auth_module
from app.core.auth import decode_access_token
from app.core.config import Settings
from app.core.errors import Unauthorized


def test_decode_access_token_returns_principal() -> None:
    user_id = uuid4()
    secret = "a" * 32
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": "user@example.com",
            "user_metadata": {"display_name": "Veljko"},
        },
        secret,
        algorithm="HS256",
    )

    principal = decode_access_token(
        token=token,
        settings=Settings(_env_file=None, supabase_jwt_secret=secret),
    )

    assert principal.user_id == user_id
    assert principal.email == "user@example.com"
    assert principal.display_name == "Veljko"


def test_decode_access_token_rejects_invalid_signature() -> None:
    good_secret = "a" * 32
    token = jwt.encode(
        {"sub": str(uuid4()), "email": "user@example.com"},
        "b" * 32,
        algorithm="HS256",
    )

    with pytest.raises(Unauthorized):
        decode_access_token(
            token=token,
            settings=Settings(_env_file=None, supabase_jwt_secret=good_secret),
        )


def test_decode_access_token_accepts_supabase_jwks_token(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    private_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": "merchant@example.com",
            "iss": "https://demo-project.supabase.co/auth/v1",
            "user_metadata": {"display_name": "Merchant Owner"},
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key"},
    )

    class FakeSigningKey:
        def __init__(self) -> None:
            self.key = private_key.public_key()

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _: str) -> FakeSigningKey:
            return FakeSigningKey()

    monkeypatch.setattr(auth_module, "_get_jwks_client", lambda _: FakeJwksClient())

    principal = decode_access_token(
        token=token,
        settings=Settings(_env_file=None, supabase_url="https://demo-project.supabase.co"),
    )

    assert principal.user_id == user_id
    assert principal.email == "merchant@example.com"
    assert principal.display_name == "Merchant Owner"


def test_decode_access_token_requires_supabase_url_for_asymmetric_tokens() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "email": "merchant@example.com",
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key"},
    )

    with pytest.raises(Unauthorized, match="SUPABASE_URL is not configured"):
        decode_access_token(token=token, settings=Settings(_env_file=None))
