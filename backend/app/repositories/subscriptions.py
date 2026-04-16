from datetime import datetime
from uuid import UUID

import asyncpg


class SubscriptionRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def create(
        self,
        *,
        merchant_account_id: UUID,
        subscriber_consumer_user_id: UUID | None,
        subscriber_email: str,
        subscriber_name: str | None,
        template: dict[str, object],
        cadence: str,
        next_run_at: datetime,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.subscriptions (
                merchant_account_id,
                subscriber_consumer_user_id,
                subscriber_email,
                subscriber_name,
                template,
                cadence,
                next_run_at
            )
            values ($1, $2, $3, $4, $5::jsonb, $6, $7)
            returning *
            """,
            merchant_account_id,
            subscriber_consumer_user_id,
            subscriber_email,
            subscriber_name,
            template,
            cadence,
            next_run_at,
        )

    async def list_for_consumer(
        self,
        *,
        user_id: UUID,
        email: str,
        limit: int,
        offset: int,
    ) -> list[asyncpg.Record]:
        return await self.connection.fetch(
            """
            select *
            from public.subscriptions
            where subscriber_consumer_user_id = $1
               or lower(subscriber_email::text) = lower($2)
            order by created_at desc
            limit $3
            offset $4
            """,
            user_id,
            email,
            limit,
            offset,
        )

    async def set_active(self, *, subscription_id: UUID, active: bool) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            update public.subscriptions
            set active = $2
            where id = $1
            returning *
            """,
            subscription_id,
            active,
        )

    async def get_for_account(self, *, subscription_id: UUID) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select *
            from public.subscriptions
            where id = $1
            """,
            subscription_id,
        )

    async def fetch_due_for_processing(self, *, limit: int) -> list[asyncpg.Record]:
        return await self.connection.fetch(
            """
            select *
            from public.subscriptions
            where active = true
              and next_run_at <= now()
            order by next_run_at asc
            for update skip locked
            limit $1
            """,
            limit,
        )

    async def advance_schedule(
        self,
        *,
        subscription_id: UUID,
        next_run_at: datetime,
        last_run_at: datetime,
    ) -> None:
        await self.connection.execute(
            """
            update public.subscriptions
            set next_run_at = $2, last_run_at = $3
            where id = $1
            """,
            subscription_id,
            next_run_at,
            last_run_at,
        )
