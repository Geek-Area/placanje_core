from datetime import datetime
from uuid import UUID

import asyncpg


class PendingInviteRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def create(
        self,
        *,
        email: str,
        merchant_account_id: UUID,
        role: str,
        token: str,
        invited_by_merchant_user_id: UUID,
        expires_at: datetime,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.pending_invites (
                email,
                merchant_account_id,
                role,
                token,
                invited_by_merchant_user_id,
                expires_at
            )
            values ($1, $2, $3, $4, $5, $6)
            returning *
            """,
            email,
            merchant_account_id,
            role,
            token,
            invited_by_merchant_user_id,
            expires_at,
        )

    async def get_active_by_token(self, *, token: str) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select *
            from public.pending_invites
            where token = $1
              and accepted_at is null
              and revoked_at is null
              and expires_at > now()
            """,
            token,
        )

    async def get_active_by_id(self, *, invite_id: UUID) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select *
            from public.pending_invites
            where id = $1
              and accepted_at is null
              and revoked_at is null
              and expires_at > now()
            """,
            invite_id,
        )

    async def mark_accepted(self, *, invite_id: UUID) -> None:
        await self.connection.execute(
            """
            update public.pending_invites
            set accepted_at = now()
            where id = $1
            """,
            invite_id,
        )

    async def mark_revoked(self, *, invite_id: UUID) -> None:
        await self.connection.execute(
            """
            update public.pending_invites
            set revoked_at = now()
            where id = $1
            """,
            invite_id,
        )
