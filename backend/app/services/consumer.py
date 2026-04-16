from typing import Any

from app.domain.auth import AuthPrincipal
from app.domain.models import (
    ConsumerProfileResponse,
    CreatePublicTransactionRequest,
    PublicTransactionCreateResponse,
    SubscriptionListResponse,
    SubscriptionSummaryResponse,
    TransactionListResponse,
    TransactionSummaryResponse,
)


class ConsumerService:
    def __init__(
        self,
        *,
        user_repository: Any,
        transaction_repository: Any,
        subscription_repository: Any,
        public_transaction_service: Any,
    ) -> None:
        self.user_repository = user_repository
        self.transaction_repository = transaction_repository
        self.subscription_repository = subscription_repository
        self.public_transaction_service = public_transaction_service

    async def get_profile(self, *, principal: AuthPrincipal) -> ConsumerProfileResponse:
        consumer_row = await self.user_repository.upsert_consumer_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )
        flags = await self.user_repository.get_profile_flags(user_id=principal.user_id)
        return ConsumerProfileResponse(
            user_id=principal.user_id,
            email=consumer_row["email"],
            display_name=consumer_row["display_name"],
            consumer_registered=bool(flags["consumer_registered"]),
            merchant_registered=bool(flags["merchant_registered"]),
        )

    async def create_regular_transaction(
        self,
        *,
        principal: AuthPrincipal,
        payload: CreatePublicTransactionRequest,
    ) -> PublicTransactionCreateResponse:
        await self.user_repository.upsert_consumer_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )
        return await self.public_transaction_service.create_consumer_regular(
            payload=payload,
            consumer_user_id=principal.user_id,
        )

    async def list_transactions(
        self,
        *,
        principal: AuthPrincipal,
        limit: int,
        offset: int,
    ) -> TransactionListResponse:
        await self.user_repository.upsert_consumer_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )
        rows = await self.transaction_repository.list_consumer_transactions(
            consumer_user_id=principal.user_id,
            limit=limit,
            offset=offset,
        )
        return TransactionListResponse(
            items=[
                TransactionSummaryResponse(
                    id=row["id"],
                    form_type=row["form_type"],
                    status=row["status"],
                    payment_ref=row["payment_ref"],
                    bank_provider=row["bank_provider"],
                    bank_credit_transfer_identificator=row["bank_credit_transfer_identificator"],
                    bank_status_code=row["bank_status_code"],
                    bank_status_description=row["bank_status_description"],
                    amount=row["amount"],
                    currency=row["currency"],
                    payment_code=row["payment_code"],
                    payment_description=row["payment_description"],
                    payee_name=row["payee_name"],
                    payee_account_number=row["payee_account_number"],
                    merchant_account_id=row["merchant_account_id"],
                    reference_model=row["reference_model"],
                    reference_number=row["reference_number"],
                    bank_transaction_ref=row["bank_transaction_ref"],
                    completed_at=row["completed_at"],
                    created_at=row["created_at"],
                )
                for row in rows
            ],
            limit=limit,
            offset=offset,
        )

    async def list_subscriptions(
        self,
        *,
        principal: AuthPrincipal,
        limit: int,
        offset: int,
    ) -> SubscriptionListResponse:
        await self.user_repository.upsert_consumer_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )
        rows = await self.subscription_repository.list_for_consumer(
            user_id=principal.user_id,
            email=principal.email,
            limit=limit,
            offset=offset,
        )
        return SubscriptionListResponse(
            items=[
                SubscriptionSummaryResponse(
                    id=row["id"],
                    merchant_account_id=row["merchant_account_id"],
                    subscriber_email=row["subscriber_email"],
                    subscriber_name=row["subscriber_name"],
                    cadence=row["cadence"],
                    next_run_at=row["next_run_at"],
                    last_run_at=row["last_run_at"],
                    active=row["active"],
                    template=row["template"],
                    created_at=row["created_at"],
                )
                for row in rows
            ],
            limit=limit,
            offset=offset,
        )
