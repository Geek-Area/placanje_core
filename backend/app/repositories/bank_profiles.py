from datetime import datetime
from uuid import UUID

import asyncpg


class MerchantBankProfileRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def upsert_profile(
        self,
        *,
        merchant_account_id: UUID,
        provider: str,
        bank_user_id: str,
        terminal_identificator: str,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.merchant_bank_profiles (
                merchant_account_id,
                provider,
                bank_user_id,
                terminal_identificator
            )
            values ($1, $2, $3, $4)
            on conflict (merchant_account_id) do update
            set
                provider = excluded.provider,
                bank_user_id = excluded.bank_user_id,
                terminal_identificator = excluded.terminal_identificator,
                active = true
            returning *
            """,
            merchant_account_id,
            provider,
            bank_user_id,
            terminal_identificator,
        )

    async def get_by_account_id(self, *, merchant_account_id: UUID) -> asyncpg.Record | None:
        try:
            return await self.connection.fetchrow(
                """
                select *
                from public.merchant_bank_profiles
                where merchant_account_id = $1
                  and active = true
                """,
                merchant_account_id,
            )
        except asyncpg.UndefinedTableError:
            return None


class BankSessionTokenRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def get_active_for_profile(
        self,
        *,
        merchant_bank_profile_id: UUID,
    ) -> asyncpg.Record | None:
        try:
            return await self.connection.fetchrow(
                """
                select *
                from public.bank_session_tokens
                where merchant_bank_profile_id = $1
                  and expires_at > now()
                """,
                merchant_bank_profile_id,
            )
        except asyncpg.UndefinedTableError:
            return None

    async def upsert_for_profile(
        self,
        *,
        merchant_bank_profile_id: UUID,
        session_token: str,
        expires_at: datetime,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.bank_session_tokens (
                merchant_bank_profile_id,
                session_token,
                expires_at
            )
            values ($1, $2, $3)
            on conflict (merchant_bank_profile_id) do update
            set
                session_token = excluded.session_token,
                expires_at = excluded.expires_at
            returning *
            """,
            merchant_bank_profile_id,
            session_token,
            expires_at,
        )
