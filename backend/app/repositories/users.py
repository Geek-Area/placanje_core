from uuid import UUID

import asyncpg


class UserRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def upsert_consumer_user(
        self,
        *,
        user_id: UUID,
        email: str,
        display_name: str | None,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.consumer_users (id, email, display_name, last_login_at)
            values ($1, $2, $3, now())
            on conflict (id) do update
            set
                email = excluded.email,
                display_name = coalesce(excluded.display_name, public.consumer_users.display_name),
                last_login_at = now()
            returning id, email, display_name
            """,
            user_id,
            email,
            display_name,
        )

    async def upsert_merchant_user(
        self,
        *,
        user_id: UUID,
        email: str,
        display_name: str | None,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.merchant_users (id, email, display_name, last_login_at)
            values ($1, $2, $3, now())
            on conflict (id) do update
            set
                email = excluded.email,
                display_name = coalesce(excluded.display_name, public.merchant_users.display_name),
                last_login_at = now()
            returning id, email, display_name
            """,
            user_id,
            email,
            display_name,
        )

    async def get_profile_flags(self, *, user_id: UUID) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            select
                exists(select 1 from public.consumer_users where id = $1) as consumer_registered,
                exists(select 1 from public.merchant_users where id = $1) as merchant_registered
            """,
            user_id,
        )

    async def get_consumer_user_by_email(self, *, email: str) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select id, email, display_name
            from public.consumer_users
            where email = $1
            """,
            email,
        )

    async def get_merchant_user_by_email(self, *, email: str) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select id, email, display_name
            from public.merchant_users
            where email = $1
            """,
            email,
        )
