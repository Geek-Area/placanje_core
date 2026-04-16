import ssl
from functools import lru_cache
from typing import Any, cast
from uuid import UUID

import certifi
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from app.core.config import Settings
from app.core.errors import AppError, Unauthorized
from app.domain.auth import AuthPrincipal

bearer_scheme = HTTPBearer(auto_error=False)
SUPPORTED_HMAC_ALGORITHMS = {"HS256", "HS384", "HS512"}
SUPPORTED_ASYMMETRIC_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"}


def _expected_issuer(settings: Settings) -> str | None:
    if settings.supabase_url is None:
        return None
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


def _jwks_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


@lru_cache(maxsize=8)
def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(
        jwks_url,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=600,
        timeout=5,
        ssl_context=_jwks_ssl_context(),
    )


def _decode_claims(
    *, token: str, key: Any, algorithm: str, issuer: str | None
) -> dict[str, Any]:
    options = cast(Any, {"verify_aud": False, "verify_iss": issuer is not None})
    claims = jwt.decode(token, key, algorithms=[algorithm], options=options, issuer=issuer)
    return claims


def decode_access_token(*, token: str, settings: Settings) -> AuthPrincipal:
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise Unauthorized("Invalid access token.") from exc

    algorithm = header.get("alg")
    if not isinstance(algorithm, str):
        raise Unauthorized("Access token header is missing the signing algorithm.")

    try:
        if algorithm in SUPPORTED_HMAC_ALGORITHMS:
            if settings.supabase_jwt_secret is None:
                raise Unauthorized(
                    "SUPABASE_JWT_SECRET is not configured for HMAC token verification."
                )
            claims = _decode_claims(
                token=token,
                key=settings.supabase_jwt_secret,
                algorithm=algorithm,
                issuer=None,
            )
        elif algorithm in SUPPORTED_ASYMMETRIC_ALGORITHMS:
            if settings.supabase_url is None:
                raise Unauthorized("SUPABASE_URL is not configured for JWKS token verification.")
            signing_key = _get_jwks_client(settings.supabase_url).get_signing_key_from_jwt(token)
            claims = _decode_claims(
                token=token,
                key=signing_key.key,
                algorithm=algorithm,
                issuer=_expected_issuer(settings),
            )
        else:
            raise Unauthorized(f"Unsupported access token algorithm: {algorithm}.")
    except PyJWKClientConnectionError as exc:
        raise AppError(
            "Could not fetch Supabase signing keys. "
            "Check local TLS certificates and network access."
        ) from exc
    except InvalidTokenError as exc:
        raise Unauthorized("Invalid access token.") from exc

    subject = claims.get("sub")
    email = claims.get("email")
    if not isinstance(subject, str) or not isinstance(email, str):
        raise Unauthorized("Access token is missing required claims.")

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise Unauthorized("Access token subject is invalid.") from exc

    display_name = claims.get("user_metadata", {}).get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        display_name = None

    return AuthPrincipal(
        user_id=user_id,
        email=email.strip().lower(),
        display_name=display_name,
        raw_claims=claims,
    )


def require_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Unauthorized("Missing bearer token.")
    return credentials.credentials
