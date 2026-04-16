from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class AuthPrincipal:
    user_id: UUID
    email: str
    display_name: str | None
    raw_claims: dict[str, object]
