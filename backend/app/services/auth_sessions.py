import httpx

from app.core.errors import Unauthorized


class AuthSessionService:
    def __init__(self, *, supabase_url: str | None, timeout_seconds: int = 15) -> None:
        self.supabase_url = supabase_url.rstrip("/") if supabase_url else None
        self.timeout_seconds = timeout_seconds

    async def revoke_current_session(
        self,
        *,
        access_token: str,
        scope: str = "global",
    ) -> dict[str, str]:
        if self.supabase_url is None:
            raise Unauthorized("SUPABASE_URL is not configured for logout.")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.supabase_url}/auth/v1/logout",
                params={"scope": scope},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        response.raise_for_status()
        return {"status": "revoked", "scope": scope}
