from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class AuthPrincipal:
    user_id: UUID
    email: str
    display_name: str | None
    raw_claims: dict[str, object]


@dataclass(slots=True)
class PosSessionPrincipal:
    credential_id: UUID
    merchant_account_id: UUID
    username: str
