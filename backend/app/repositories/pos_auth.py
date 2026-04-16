from datetime import datetime
from uuid import UUID

import asyncpg


class MerchantPosAuthRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def upsert_credentials(
        self,
        *,
        merchant_account_id: UUID,
        username: str,
        password_hash: str,
        password_salt: str,
        created_by_merchant_user_id: UUID | None,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.merchant_pos_credentials (
                merchant_account_id,
                username,
                password_hash,
                password_salt,
                created_by_merchant_user_id
            )
            values ($1, $2, $3, $4, $5)
            on conflict (merchant_account_id) do update
            set
                username = excluded.username,
                password_hash = excluded.password_hash,
                password_salt = excluded.password_salt,
                active = true,
                created_by_merchant_user_id = excluded.created_by_merchant_user_id
            returning *
            """,
            merchant_account_id,
            username,
            password_hash,
            password_salt,
            created_by_merchant_user_id,
        )

    async def get_credentials_by_username(self, *, username: str) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select
                pc.*,
                pc.active as credential_active,
                ma.display_name,
                ma.account_type,
                ma.payee_name,
                ma.payee_account_number,
                ma.payee_address,
                ma.payee_city,
                ma.mcc,
                ma.active as merchant_account_active
            from public.merchant_pos_credentials pc
            join public.merchant_accounts ma on ma.id = pc.merchant_account_id
            where pc.username = $1
            """,
            username,
        )

    async def create_session(
        self,
        *,
        merchant_pos_credential_id: UUID,
        session_token_hash: str,
        expires_at: datetime,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.merchant_pos_sessions (
                merchant_pos_credential_id,
                session_token_hash,
                expires_at,
                last_used_at
            )
            values ($1, $2, $3, now())
            returning *
            """,
            merchant_pos_credential_id,
            session_token_hash,
            expires_at,
        )

    async def get_active_session(self, *, session_token_hash: str) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select
                ps.id as session_id,
                ps.merchant_pos_credential_id,
                ps.expires_at,
                pc.username,
                pc.active as credential_active,
                pc.merchant_account_id,
                ma.display_name,
                ma.account_type,
                ma.payee_name,
                ma.payee_account_number,
                ma.payee_address,
                ma.payee_city,
                ma.mcc,
                ma.active as merchant_account_active
            from public.merchant_pos_sessions ps
            join public.merchant_pos_credentials pc
              on pc.id = ps.merchant_pos_credential_id
            join public.merchant_accounts ma
              on ma.id = pc.merchant_account_id
            where ps.session_token_hash = $1
              and ps.revoked_at is null
              and ps.expires_at > now()
            """,
            session_token_hash,
        )

    async def touch_session(self, *, session_id: UUID) -> None:
        await self.connection.execute(
            """
            update public.merchant_pos_sessions
            set last_used_at = now()
            where id = $1
            """,
            session_id,
        )

    async def touch_last_login(self, *, credential_id: UUID) -> None:
        await self.connection.execute(
            """
            update public.merchant_pos_credentials
            set last_login_at = now()
            where id = $1
            """,
            credential_id,
        )

    async def revoke_session(self, *, session_token_hash: str) -> None:
        await self.connection.execute(
            """
            update public.merchant_pos_sessions
            set revoked_at = now()
            where session_token_hash = $1
              and revoked_at is null
            """,
            session_token_hash,
        )
