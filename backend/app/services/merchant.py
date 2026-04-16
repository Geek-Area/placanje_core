import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg

from app.core.errors import NotFound, Unauthorized, ValidationFailed
from app.domain.auth import AuthPrincipal
from app.domain.enums import AccountType, MembershipRole, MembershipScope
from app.domain.models import (
    AcceptInviteResponse,
    CreatePosTransactionRequest,
    MerchantAccountCreateRequest,
    MerchantAccountListResponse,
    MerchantAccountResponse,
    MerchantAccountStatsResponse,
    MerchantInviteRequest,
    MerchantInviteResponse,
    MerchantSignupRequest,
    MerchantTransactionCreateResponse,
    TransactionListResponse,
    TransactionSummaryResponse,
)

ROLE_RANK = {
    MembershipRole.VIEWER.value: 1,
    MembershipRole.OPERATOR.value: 2,
    MembershipRole.ADMIN.value: 3,
    MembershipRole.OWNER.value: 4,
}


def _slugify(value: str) -> str:
    normalized = [character.lower() if character.isalnum() else "-" for character in value.strip()]
    slug = "".join(normalized).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug[:48].strip("-")
    return slug or "account"


class MerchantService:
    def __init__(
        self,
        *,
        user_repository: Any,
        merchant_account_repository: Any,
        invite_repository: Any,
        transaction_repository: Any,
        transaction_service: Any,
        connection: asyncpg.Connection,
    ) -> None:
        self.user_repository = user_repository
        self.merchant_account_repository = merchant_account_repository
        self.invite_repository = invite_repository
        self.transaction_repository = transaction_repository
        self.transaction_service = transaction_service
        self.connection = connection

    async def signup_owner(
        self,
        *,
        principal: AuthPrincipal,
        payload: MerchantSignupRequest,
    ) -> MerchantAccountResponse:
        await self.user_repository.upsert_merchant_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )

        async with self.connection.transaction():
            account = await self.merchant_account_repository.create_account(
                parent_account_id=None,
                account_type=AccountType.ORGANIZATION.value,
                slug=self._unique_slug(payload.slug, payload.display_name),
                display_name=payload.display_name,
                legal_entity_name=payload.legal_entity_name,
                legal_entity_id=payload.legal_entity_id,
                payee_account_number=payload.payee_account_number,
                payee_name=payload.payee_name or payload.display_name,
                payee_address=payload.payee_address,
                payee_city=payload.payee_city,
                subscription_tier=payload.subscription_tier,
            )
            await self.merchant_account_repository.create_membership(
                merchant_user_id=principal.user_id,
                merchant_account_id=account["id"],
                role=MembershipRole.OWNER.value,
                scope=MembershipScope.ACCOUNT_AND_DESCENDANTS.value,
            )
        return self._account_response(account, MembershipRole.OWNER.value)

    async def list_accounts(self, *, principal: AuthPrincipal) -> MerchantAccountListResponse:
        await self.user_repository.upsert_merchant_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )
        rows = await self.merchant_account_repository.list_visible_accounts(
            user_id=principal.user_id
        )
        return MerchantAccountListResponse(
            items=[self._account_response(row, row["effective_role"]) for row in rows]
        )

    async def create_sub_account(
        self,
        *,
        principal: AuthPrincipal,
        parent_account_id: UUID,
        payload: MerchantAccountCreateRequest,
    ) -> MerchantAccountResponse:
        parent = await self._get_manageable_account(
            principal=principal,
            account_id=parent_account_id,
            minimum_role=MembershipRole.ADMIN.value,
        )
        account = await self.merchant_account_repository.create_account(
            parent_account_id=parent_account_id,
            account_type=AccountType.POS.value,
            slug=self._unique_slug(payload.slug, payload.display_name),
            display_name=payload.display_name,
            legal_entity_name=None,
            legal_entity_id=None,
            payee_account_number=payload.payee_account_number or parent["payee_account_number"],
            payee_name=payload.payee_name or payload.display_name,
            payee_address=payload.payee_address,
            payee_city=payload.payee_city,
            subscription_tier=None,
        )
        return self._account_response(account, MembershipRole.ADMIN.value)

    async def invite_cashier(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
        payload: MerchantInviteRequest,
    ) -> MerchantInviteResponse:
        await self._get_manageable_account(
            principal=principal,
            account_id=account_id,
            minimum_role=MembershipRole.ADMIN.value,
        )
        existing_merchant_user = await self.user_repository.get_merchant_user_by_email(
            email=payload.email
        )
        if existing_merchant_user is not None:
            await self.merchant_account_repository.create_membership(
                merchant_user_id=existing_merchant_user["id"],
                merchant_account_id=account_id,
                role=payload.role,
                scope=MembershipScope.ACCOUNT_ONLY.value,
            )
            return MerchantInviteResponse(
                status="added",
                invitation_mode="direct_membership",
                account_id=account_id,
                invited_email=payload.email,
                role=payload.role,
                token=None,
            )

        token = secrets.token_urlsafe(24)
        await self.invite_repository.create(
            email=payload.email,
            merchant_account_id=account_id,
            role=payload.role,
            token=token,
            invited_by_merchant_user_id=principal.user_id,
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
        )
        return MerchantInviteResponse(
            status="pending",
            invitation_mode="token",
            account_id=account_id,
            invited_email=payload.email,
            role=payload.role,
            token=token,
        )

    async def accept_invite(
        self,
        *,
        principal: AuthPrincipal,
        token: str,
    ) -> AcceptInviteResponse:
        invite = await self.invite_repository.get_active_by_token(token=token)
        if invite is None:
            raise NotFound("Invite token does not exist or has expired.")
        if principal.email != invite["email"]:
            raise Unauthorized("Invite token is not valid for the current user.")

        async with self.connection.transaction():
            await self.user_repository.upsert_merchant_user(
                user_id=principal.user_id,
                email=principal.email,
                display_name=principal.display_name,
            )
            await self.merchant_account_repository.create_membership(
                merchant_user_id=principal.user_id,
                merchant_account_id=invite["merchant_account_id"],
                role=invite["role"],
                scope=MembershipScope.ACCOUNT_ONLY.value,
            )
            await self.invite_repository.mark_accepted(invite_id=invite["id"])
        return AcceptInviteResponse(
            status="accepted",
            account_id=invite["merchant_account_id"],
            role=invite["role"],
        )

    async def create_pos_transaction(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
        payload: CreatePosTransactionRequest,
    ) -> MerchantTransactionCreateResponse:
        account = await self._get_manageable_account(
            principal=principal,
            account_id=account_id,
            minimum_role=MembershipRole.OPERATOR.value,
        )
        if account["payee_account_number"] is None:
            raise ValidationFailed("Merchant account is missing a payee account number.")
        return await self.transaction_service.create_pos_draft(
            merchant_account_id=account["id"],
            account_display_name=account["display_name"],
            payee_name=account["payee_name"],
            payee_address=account["payee_address"],
            payee_city=account["payee_city"],
            payee_account_number=account["payee_account_number"],
            payload=payload,
        )

    async def list_account_transactions(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
        limit: int,
        offset: int,
    ) -> TransactionListResponse:
        await self._get_visible_account(principal=principal, account_id=account_id)
        rows = await self.transaction_repository.list_account_transactions(
            merchant_account_id=account_id,
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

    async def get_account_stats(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
    ) -> MerchantAccountStatsResponse:
        await self._get_visible_account(principal=principal, account_id=account_id)
        stats = await self.transaction_repository.account_stats(merchant_account_id=account_id)
        return MerchantAccountStatsResponse(
            account_id=account_id,
            total_transactions=stats["total_transactions"],
            completed_transactions=stats["completed_transactions"],
            awaiting_payment_transactions=stats["awaiting_payment_transactions"],
            expired_transactions=stats["expired_transactions"],
            total_completed_amount=stats["total_completed_amount"],
        )

    async def _get_visible_account(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
    ) -> Any:
        await self.user_repository.upsert_merchant_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )
        allowed = await self.merchant_account_repository.list_account_transactions_allowed(
            user_id=principal.user_id,
            account_id=account_id,
        )
        if not allowed:
            raise NotFound("Merchant account does not exist.")
        account = await self.merchant_account_repository.get_account(account_id=account_id)
        if account is None:
            raise NotFound("Merchant account does not exist.")
        return account

    async def _get_manageable_account(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
        minimum_role: str,
    ) -> Any:
        account = await self._get_visible_account(principal=principal, account_id=account_id)
        role = await self.merchant_account_repository.get_effective_role(
            user_id=principal.user_id,
            account_id=account_id,
        )
        if role is None or ROLE_RANK[role] < ROLE_RANK[minimum_role]:
            raise NotFound("Merchant account does not exist.")
        return account

    @staticmethod
    def _unique_slug(explicit_slug: str | None, display_name: str) -> str:
        base = explicit_slug or _slugify(display_name)
        suffix = secrets.token_hex(3)
        return f"{base}-{suffix}"

    @staticmethod
    def _account_response(row: Any, effective_role: str | None) -> MerchantAccountResponse:
        return MerchantAccountResponse(
            id=row["id"],
            parent_account_id=row["parent_account_id"],
            account_type=row["account_type"],
            slug=row["slug"],
            display_name=row["display_name"],
            payee_name=row["payee_name"],
            payee_account_number=row["payee_account_number"],
            payee_address=row["payee_address"],
            payee_city=row["payee_city"],
            active=row["active"],
            effective_role=effective_role,
        )
