import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.core.errors import NotFound, ValidationFailed
from app.domain.auth import AuthPrincipal
from app.domain.enums import MembershipRole, SubscriptionCadence
from app.domain.models import (
    CreateSubscriptionRequest,
    SubscriptionMutationResponse,
    SubscriptionSummaryResponse,
)
from app.domain.qr import build_nbs_ips_qr_string
from app.services.merchant import ROLE_RANK


class SubscriptionService:
    def __init__(
        self,
        *,
        user_repository: Any,
        merchant_account_repository: Any,
        subscription_repository: Any,
        transaction_repository: Any,
        share_link_repository: Any,
        connection: Any,
        share_link_ttl_days: int,
    ) -> None:
        self.user_repository = user_repository
        self.merchant_account_repository = merchant_account_repository
        self.subscription_repository = subscription_repository
        self.transaction_repository = transaction_repository
        self.share_link_repository = share_link_repository
        self.connection = connection
        self.share_link_ttl_days = share_link_ttl_days

    async def create(
        self,
        *,
        principal: AuthPrincipal,
        account_id: Any,
        payload: CreateSubscriptionRequest,
    ) -> SubscriptionSummaryResponse:
        account = await self._get_manageable_account(
            principal=principal,
            account_id=account_id,
            minimum_role=MembershipRole.ADMIN.value,
        )
        if account["payee_account_number"] is None:
            raise ValidationFailed("Merchant account is missing a payee account number.")
        consumer = await self.user_repository.get_consumer_user_by_email(
            email=payload.subscriber_email
        )
        template = {
            "amount": str(payload.amount),
            "currency": payload.currency,
            "payment_code": payload.payment_code,
            "reference_model": payload.reference_model,
            "reference_number": payload.reference_number,
            "payment_description": payload.payment_description,
            "payee_name": account["payee_name"],
            "payee_address": account["payee_address"],
            "payee_city": account["payee_city"],
            "payee_account_number": account["payee_account_number"],
        }
        row = await self.subscription_repository.create(
            merchant_account_id=account_id,
            subscriber_consumer_user_id=None if consumer is None else consumer["id"],
            subscriber_email=payload.subscriber_email,
            subscriber_name=payload.subscriber_name,
            template=template,
            cadence=payload.cadence,
            next_run_at=payload.first_run_at,
        )
        return SubscriptionSummaryResponse(
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

    async def pause(
        self,
        *,
        principal: AuthPrincipal,
        subscription_id: Any,
    ) -> SubscriptionMutationResponse:
        subscription = await self._get_manageable_subscription(
            principal=principal,
            subscription_id=subscription_id,
            minimum_role=MembershipRole.ADMIN.value,
        )
        row = await self.subscription_repository.set_active(
            subscription_id=subscription["id"],
            active=False,
        )
        if row is None:
            raise NotFound("Subscription does not exist.")
        return SubscriptionMutationResponse(
            id=row["id"], active=row["active"], next_run_at=row["next_run_at"]
        )

    async def resume(
        self,
        *,
        principal: AuthPrincipal,
        subscription_id: Any,
    ) -> SubscriptionMutationResponse:
        subscription = await self._get_manageable_subscription(
            principal=principal,
            subscription_id=subscription_id,
            minimum_role=MembershipRole.ADMIN.value,
        )
        row = await self.subscription_repository.set_active(
            subscription_id=subscription["id"],
            active=True,
        )
        if row is None:
            raise NotFound("Subscription does not exist.")
        return SubscriptionMutationResponse(
            id=row["id"], active=row["active"], next_run_at=row["next_run_at"]
        )

    async def run_due(self, *, limit: int = 100) -> int:
        async with self.connection.transaction():
            rows = await self.subscription_repository.fetch_due_for_processing(limit=limit)
            now = datetime.now(tz=UTC)
            processed = 0
            for row in rows:
                template = row["template"]
                amount = Decimal(str(template["amount"]))
                qr_string = build_nbs_ips_qr_string(
                    payee_account_number=template["payee_account_number"],
                    payee_name=template["payee_name"],
                    payee_address=template.get("payee_address"),
                    payee_city=template.get("payee_city"),
                    amount=amount,
                    currency=template["currency"],
                    payment_code=template["payment_code"],
                    payment_description=template.get("payment_description"),
                    payer_name=row["subscriber_name"],
                    payer_address=None,
                    payer_city=None,
                    reference_model=template.get("reference_model"),
                    reference_number=template.get("reference_number"),
                )
                payment_ref = f"PLC-{secrets.token_hex(8).upper()}"
                transaction = await self.transaction_repository.create_subscription_run(
                    merchant_account_id=row["merchant_account_id"],
                    subscription_id=row["id"],
                    consumer_user_id=row["subscriber_consumer_user_id"],
                    payer_name=row["subscriber_name"],
                    payee_name=template["payee_name"],
                    payee_address=template.get("payee_address"),
                    payee_city=template.get("payee_city"),
                    payee_account_number=template["payee_account_number"],
                    amount=amount,
                    currency=template["currency"],
                    payment_code=template["payment_code"],
                    reference_model=template.get("reference_model"),
                    reference_number=template.get("reference_number"),
                    payment_description=template.get("payment_description"),
                    qr_string=qr_string,
                    payment_ref=payment_ref,
                )
                await self.share_link_repository.create(
                    transaction_id=transaction["id"],
                    slug=secrets.token_urlsafe(8).rstrip("=").replace("-", "x").replace("_", "y"),
                    qr_string=qr_string,
                    expires_at=now + timedelta(days=self.share_link_ttl_days),
                )
                await self.subscription_repository.advance_schedule(
                    subscription_id=row["id"],
                    next_run_at=self._advance_cadence(row["next_run_at"], row["cadence"]),
                    last_run_at=now,
                )
                processed += 1
            return processed

    async def _get_manageable_subscription(
        self,
        *,
        principal: AuthPrincipal,
        subscription_id: Any,
        minimum_role: str,
    ) -> Any:
        subscription = await self.subscription_repository.get_for_account(
            subscription_id=subscription_id
        )
        if subscription is None:
            raise NotFound("Subscription does not exist.")
        await self._get_manageable_account(
            principal=principal,
            account_id=subscription["merchant_account_id"],
            minimum_role=minimum_role,
        )
        return subscription

    async def _get_manageable_account(
        self,
        *,
        principal: AuthPrincipal,
        account_id: Any,
        minimum_role: str,
    ) -> Any:
        await self.user_repository.upsert_merchant_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )
        role = await self.merchant_account_repository.get_effective_role(
            user_id=principal.user_id,
            account_id=account_id,
        )
        if role is None or ROLE_RANK[role] < ROLE_RANK[minimum_role]:
            raise NotFound("Merchant account does not exist.")
        account = await self.merchant_account_repository.get_account(account_id=account_id)
        if account is None:
            raise NotFound("Merchant account does not exist.")
        return account

    @staticmethod
    def _advance_cadence(value: datetime, cadence: str) -> datetime:
        if cadence == SubscriptionCadence.DAILY.value:
            return value + timedelta(days=1)
        if cadence == SubscriptionCadence.WEEKLY.value:
            return value + timedelta(weeks=1)
        if cadence == SubscriptionCadence.MONTHLY.value:
            month = value.month + 1
            year = value.year
            if month == 13:
                month = 1
                year += 1
            day = min(value.day, 28)
            return value.replace(year=year, month=month, day=day)
        raise ValidationFailed("Unsupported subscription cadence.", details={"cadence": cadence})
