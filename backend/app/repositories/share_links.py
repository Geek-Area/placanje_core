from datetime import datetime
from uuid import UUID

import asyncpg


class ShareLinkRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def create(
        self,
        *,
        transaction_id: UUID,
        slug: str,
        qr_string: str,
        expires_at: datetime,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.share_links (
                transaction_id,
                slug,
                qr_string,
                expires_at
            )
            values ($1, $2, $3, $4)
            returning slug, expires_at
            """,
            transaction_id,
            slug,
            qr_string,
            expires_at,
        )

    async def increment_access_count(self, *, slug: str) -> None:
        await self.connection.execute(
            """
            update public.share_links
            set accessed_count = accessed_count + 1
            where slug = $1
            """,
            slug,
        )
