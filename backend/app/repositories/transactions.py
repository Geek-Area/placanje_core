from datetime import datetime
from decimal import Decimal
from uuid import UUID

import asyncpg

from app.domain.enums import FormType, TransactionStatus
from app.domain.models import CreatePosTransactionRequest, CreatePublicTransactionRequest


class TransactionRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self.connection = connection

    async def create_regular(
        self,
        *,
        payload: CreatePublicTransactionRequest,
        qr_string: str,
        payment_ref: str,
        consumer_user_id: UUID | None,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.transactions (
                form_type,
                status,
                payment_ref,
                consumer_user_id,
                payer_name,
                payer_address,
                payer_city,
                payee_name,
                payee_address,
                payee_city,
                payee_account_number,
                amount,
                currency,
                payment_code,
                reference_model,
                reference_number,
                payment_description,
                ips_qr_payload
            )
            values (
                $1, $2, $3, $4, $5, $6, $7, $8, $9,
                $10, $11, $12, $13, $14, $15, $16, $17, $18
            )
            returning id, created_at, status, payment_ref
            """,
            FormType.REGULAR.value,
            TransactionStatus.DRAFT.value,
            payment_ref,
            consumer_user_id,
            payload.payer_name,
            payload.payer_address,
            payload.payer_city,
            payload.payee_name,
            payload.payee_address,
            payload.payee_city,
            payload.payee_account_number,
            payload.amount,
            payload.currency,
            payload.payment_code,
            payload.reference_model,
            payload.reference_number,
            payload.payment_description,
            qr_string,
        )

    async def create_pos_draft(
        self,
        *,
        merchant_account_id: UUID,
        account_display_name: str,
        payee_name: str,
        payee_address: str | None,
        payee_city: str | None,
        payee_account_number: str,
        payload: CreatePosTransactionRequest,
        qr_string: str,
        payment_ref: str,
        payment_code: str,
        bank_provider: str | None,
        bank_credit_transfer_identificator: str | None,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.transactions (
                form_type,
                status,
                payment_ref,
                bank_provider,
                bank_credit_transfer_identificator,
                merchant_account_id,
                payee_name,
                payee_address,
                payee_city,
                payee_account_number,
                amount,
                currency,
                payment_code,
                reference_model,
                reference_number,
                payment_description,
                ips_qr_payload,
                metadata
            )
            values (
                $1, $2, $3, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14, $15, $16, $17,
                jsonb_build_object('merchant_account_display_name', $18::text)
            )
            returning id, created_at, status, payment_ref, bank_credit_transfer_identificator
            """,
            FormType.IPS.value,
            TransactionStatus.AWAITING_PAYMENT.value,
            payment_ref,
            bank_provider,
            bank_credit_transfer_identificator,
            merchant_account_id,
            payee_name,
            payee_address,
            payee_city,
            payee_account_number,
            payload.amount,
            "RSD",
            payment_code,
            payload.reference_model,
            payload.reference_number,
            payload.payment_description,
            qr_string,
            account_display_name,
        )

    async def create_request_to_pay(
        self,
        *,
        merchant_account_id: UUID,
        account_display_name: str,
        payee_name: str,
        payee_address: str | None,
        payee_city: str | None,
        payee_account_number: str,
        payer_name: str | None,
        payer_address: str | None,
        payer_city: str | None,
        amount: Decimal,
        payment_description: str | None,
        payment_ref: str,
        payment_code: str,
        bank_provider: str,
        bank_credit_transfer_identificator: str,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.transactions (
                form_type,
                status,
                payment_ref,
                bank_provider,
                bank_credit_transfer_identificator,
                merchant_account_id,
                payer_name,
                payer_address,
                payer_city,
                payee_name,
                payee_address,
                payee_city,
                payee_account_number,
                amount,
                currency,
                payment_code,
                payment_description,
                ips_qr_payload,
                metadata
            )
            values (
                $1, $2, $3, $4, $5, $6, $7, $8, $9,
                $10, $11, $12, $13, $14, $15, $16, $17, $18,
                jsonb_build_object(
                    'merchant_account_display_name', $19::text,
                    'payment_flow', 'request_to_pay'
                )
            )
            returning id, created_at, status, payment_ref, bank_credit_transfer_identificator
            """,
            FormType.IPS.value,
            TransactionStatus.AWAITING_PAYMENT.value,
            payment_ref,
            bank_provider,
            bank_credit_transfer_identificator,
            merchant_account_id,
            payer_name,
            payer_address,
            payer_city,
            payee_name,
            payee_address,
            payee_city,
            payee_account_number,
            amount,
            "RSD",
            payment_code,
            payment_description,
            "",
            account_display_name,
        )

    async def create_subscription_run(
        self,
        *,
        merchant_account_id: UUID,
        subscription_id: UUID,
        consumer_user_id: UUID | None,
        payer_name: str | None,
        payee_name: str,
        payee_address: str | None,
        payee_city: str | None,
        payee_account_number: str,
        amount: Decimal,
        currency: str,
        payment_code: str,
        reference_model: str | None,
        reference_number: str | None,
        payment_description: str | None,
        qr_string: str,
        payment_ref: str,
    ) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            insert into public.transactions (
                form_type,
                status,
                payment_ref,
                consumer_user_id,
                merchant_account_id,
                subscription_id,
                payer_name,
                payee_name,
                payee_address,
                payee_city,
                payee_account_number,
                amount,
                currency,
                payment_code,
                reference_model,
                reference_number,
                payment_description,
                ips_qr_payload
            )
            values (
                $1, $2, $3, $4, $5, $6, $7,
                $8, $9, $10, $11, $12, $13, $14,
                $15, $16, $17, $18
            )
            returning id, created_at, status, payment_ref
            """,
            FormType.SUBSCRIPTION.value,
            TransactionStatus.DRAFT.value,
            payment_ref,
            consumer_user_id,
            merchant_account_id,
            subscription_id,
            payer_name,
            payee_name,
            payee_address,
            payee_city,
            payee_account_number,
            amount,
            currency,
            payment_code,
            reference_model,
            reference_number,
            payment_description,
            qr_string,
        )

    async def get_public_share_payload(self, *, slug: str) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select
                t.id as transaction_id,
                t.payment_ref,
                t.form_type,
                t.status,
                t.payer_name,
                t.payer_address,
                t.payer_city,
                t.payee_name,
                t.payee_address,
                t.payee_city,
                t.payee_account_number,
                t.amount,
                t.currency,
                t.payment_code,
                t.reference_model,
                t.reference_number,
                t.payment_description,
                s.qr_string,
                s.expires_at,
                s.revoked_at
            from public.share_links s
            join public.transactions t on t.id = s.transaction_id
            where s.slug = $1
            """,
            slug,
        )

    async def list_consumer_transactions(
        self,
        *,
        consumer_user_id: UUID,
        limit: int,
        offset: int,
    ) -> list[asyncpg.Record]:
        return await self.connection.fetch(
            """
            select
                id,
                form_type,
                status,
                payment_ref,
                bank_provider,
                bank_credit_transfer_identificator,
                bank_status_code,
                bank_status_description,
                amount,
                currency,
                payment_code,
                payment_description,
                payee_name,
                payee_account_number,
                merchant_account_id,
                reference_model,
                reference_number,
                bank_transaction_ref,
                completed_at,
                created_at
            from public.transactions
            where consumer_user_id = $1
            order by created_at desc
            limit $2
            offset $3
            """,
            consumer_user_id,
            limit,
            offset,
        )

    async def list_account_transactions(
        self,
        *,
        merchant_account_id: UUID,
        limit: int,
        offset: int,
    ) -> list[asyncpg.Record]:
        return await self.connection.fetch(
            """
            select
                id,
                form_type,
                status,
                payment_ref,
                bank_provider,
                bank_credit_transfer_identificator,
                bank_status_code,
                bank_status_description,
                amount,
                currency,
                payment_code,
                payment_description,
                payee_name,
                payee_account_number,
                merchant_account_id,
                reference_model,
                reference_number,
                bank_transaction_ref,
                completed_at,
                created_at
            from public.transactions
            where merchant_account_id = $1
            order by created_at desc
            limit $2
            offset $3
            """,
            merchant_account_id,
            limit,
            offset,
        )

    async def account_stats(self, *, merchant_account_id: UUID) -> asyncpg.Record:
        return await self.connection.fetchrow(
            """
            select
                count(*)::int as total_transactions,
                count(*) filter (where status = 'completed')::int as completed_transactions,
                count(*) filter (
                    where status = 'awaiting_payment'
                )::int as awaiting_payment_transactions,
                count(*) filter (where status = 'expired')::int as expired_transactions,
                coalesce(sum(amount) filter (where status = 'completed'), 0)::numeric(18,2)
                  as total_completed_amount
            from public.transactions
            where merchant_account_id = $1
            """,
            merchant_account_id,
        )

    async def get_account_transaction(
        self,
        *,
        merchant_account_id: UUID,
        transaction_id: UUID,
    ) -> asyncpg.Record | None:
        return await self.connection.fetchrow(
            """
            select *
            from public.transactions
            where merchant_account_id = $1
              and id = $2
            """,
            merchant_account_id,
            transaction_id,
        )

    async def next_bank_transaction_counter(self) -> int:
        row = await self.connection.fetchrow(
            """
            select nextval('public.bank_credit_transfer_counter_seq')::bigint as value
            """
        )
        return int(row["value"])

    async def mark_payment_completed(
        self,
        *,
        payment_ref: str,
        bank_transaction_ref: str,
        completed_at: str,
    ) -> str:
        return await self.connection.execute(
            """
            update public.transactions
            set
                status = 'completed',
                bank_transaction_ref = $2,
                completed_at = $3
            where payment_ref = $1
              and status = 'awaiting_payment'
            """,
            payment_ref,
            bank_transaction_ref,
            completed_at,
        )

    async def update_bank_status(
        self,
        *,
        transaction_id: UUID,
        bank_status_code: str,
        bank_status_description: str | None,
        checked_at: datetime,
    ) -> str:
        return await self.connection.execute(
            """
            update public.transactions
            set
                bank_status_code = $2,
                bank_status_description = $3,
                bank_status_checked_at = $4
            where id = $1
            """,
            transaction_id,
            bank_status_code,
            bank_status_description,
            checked_at,
        )

    async def mark_transaction_completed(
        self,
        *,
        transaction_id: UUID,
        bank_transaction_ref: str,
        completed_at: datetime,
        bank_status_code: str,
        bank_status_description: str | None,
    ) -> str:
        return await self.connection.execute(
            """
            update public.transactions
            set
                status = 'completed',
                bank_transaction_ref = $2,
                completed_at = $3,
                bank_status_code = $4,
                bank_status_description = $5,
                bank_status_checked_at = now()
            where id = $1
            """,
            transaction_id,
            bank_transaction_ref,
            completed_at,
            bank_status_code,
            bank_status_description,
        )

    async def mark_transaction_failed(
        self,
        *,
        transaction_id: UUID,
        bank_status_code: str,
        bank_status_description: str | None,
    ) -> str:
        return await self.connection.execute(
            """
            update public.transactions
            set
                status = 'failed',
                bank_status_code = $2,
                bank_status_description = $3,
                bank_status_checked_at = now()
            where id = $1
            """,
            transaction_id,
            bank_status_code,
            bank_status_description,
        )

    async def expire_awaiting_payment_transactions(self, *, older_than: datetime) -> str:
        return await self.connection.execute(
            """
            update public.transactions
            set status = 'expired'
            where status = 'awaiting_payment'
              and form_type = 'ips'
              and created_at < $1
            """,
            older_than,
        )
