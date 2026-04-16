from uuid import UUID

import asyncpg


class MerchantAccountRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def create_account(
        self,
        *,
        parent_account_id: UUID | None,
        account_type: str,
        slug: str,
        display_name: str,
        legal_entity_name: str | None,
        legal_entity_id: str | None,
        payee_account_number: str | None,
        payee_name: str,
        payee_address: str | None,
        payee_city: str | None,
        mcc: str | None,
        subscription_tier: str | None,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.merchant_accounts (
                parent_account_id,
                account_type,
                slug,
                display_name,
                legal_entity_name,
                legal_entity_id,
                payee_account_number,
                payee_name,
                payee_address,
                payee_city,
                mcc,
                subscription_tier
            )
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            returning *
            """,
            parent_account_id,
            account_type,
            slug,
            display_name,
            legal_entity_name,
            legal_entity_id,
            payee_account_number,
            payee_name,
            payee_address,
            payee_city,
            mcc,
            subscription_tier,
        )

    async def get_account(self, *, account_id: UUID) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select *
            from public.merchant_accounts
            where id = $1
            """,
            account_id,
        )

    async def list_visible_accounts(self, *, user_id: UUID) -> list[asyncpg.Record]:
        return await self.connection.fetch(
            """
            with visible_accounts as (
                select account_id from public.visible_merchant_accounts($1)
            ),
            effective_roles as (
                select
                    visible.account_id,
                    (
                        with recursive ancestors as (
                            select ma.id, ma.parent_account_id
                            from public.merchant_accounts ma
                            where ma.id = visible.account_id
                            union all
                            select parent.id, parent.parent_account_id
                            from public.merchant_accounts parent
                            join ancestors on ancestors.parent_account_id = parent.id
                        )
                        select mm.role
                        from public.merchant_memberships mm
                        join ancestors on ancestors.id = mm.merchant_account_id
                        where mm.merchant_user_id = $1
                          and mm.revoked_at is null
                          and (
                              mm.merchant_account_id = visible.account_id
                              or mm.scope = 'account_and_descendants'
                          )
                        order by case mm.role
                            when 'owner' then 4
                            when 'admin' then 3
                            when 'operator' then 2
                            else 1
                        end desc
                        limit 1
                    ) as effective_role
                from visible_accounts visible
            )
            select
                ma.*,
                effective_roles.effective_role
            from public.merchant_accounts ma
            join visible_accounts visible on visible.account_id = ma.id
            left join effective_roles on effective_roles.account_id = ma.id
            order by ma.created_at asc
            """,
            user_id,
        )

    async def get_effective_role(self, *, user_id: UUID, account_id: UUID) -> str | None:
        row = await self.connection.fetchrow(
            """
            with recursive ancestors as (
                select id, parent_account_id
                from public.merchant_accounts
                where id = $2
                union all
                select parent.id, parent.parent_account_id
                from public.merchant_accounts parent
                join ancestors on ancestors.parent_account_id = parent.id
            )
            select mm.role
            from public.merchant_memberships mm
            join ancestors on ancestors.id = mm.merchant_account_id
            where mm.merchant_user_id = $1
              and mm.revoked_at is null
              and (
                mm.merchant_account_id = $2
                or mm.scope = 'account_and_descendants'
              )
            order by case mm.role
                when 'owner' then 4
                when 'admin' then 3
                when 'operator' then 2
                else 1
            end desc
            limit 1
            """,
            user_id,
            account_id,
        )
        return None if row is None else row["role"]

    async def create_membership(
        self,
        *,
        merchant_user_id: UUID,
        merchant_account_id: UUID,
        role: str,
        scope: str,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.merchant_memberships (
                merchant_user_id,
                merchant_account_id,
                role,
                scope
            )
            values ($1, $2, $3, $4)
            on conflict (merchant_user_id, merchant_account_id) do update
            set
                role = excluded.role,
                scope = excluded.scope,
                revoked_at = null
            returning *
            """,
            merchant_user_id,
            merchant_account_id,
            role,
            scope,
        )

    async def list_account_transactions_allowed(self, *, user_id: UUID, account_id: UUID) -> bool:
        row = await self.connection.fetchrow(
            """
            select exists(
                select 1
                from public.visible_merchant_accounts($1)
                where account_id = $2
            ) as allowed
            """,
            user_id,
            account_id,
        )
        return bool(row["allowed"]) if row is not None else False
