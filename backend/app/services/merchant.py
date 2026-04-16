import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg

from app.core.errors import NotFound, Unauthorized, ValidationFailed
from app.core.pos_security import hash_pos_password, normalize_pos_username
from app.domain.auth import AuthPrincipal
from app.domain.bank_pos import build_credit_transfer_identificator
from app.domain.enums import AccountType, MembershipRole, MembershipScope
from app.domain.models import (
    AcceptInviteResponse,
    CreatePosTransactionRequest,
    MerchantAccountCreateRequest,
    MerchantAccountListResponse,
    MerchantAccountResponse,
    MerchantAccountStatsResponse,
    MerchantBankProfileResponse,
    MerchantBankProfileUpsertRequest,
    MerchantInviteRequest,
    MerchantInviteResponse,
    MerchantRequestToPayRequest,
    MerchantSessionResponse,
    MerchantSignupRequest,
    MerchantTransactionCreateResponse,
    PosCredentialsResponse,
    PosCredentialsUpsertRequest,
    RevokeInviteResponse,
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
        bank_profile_repository: Any,
        invite_repository: Any,
        transaction_repository: Any,
        transaction_service: Any,
        bank_pos_service: Any,
        connection: asyncpg.Connection,
        pos_auth_repository: Any | None = None,
    ) -> None:
        self.user_repository = user_repository
        self.merchant_account_repository = merchant_account_repository
        self.bank_profile_repository = bank_profile_repository
        self.invite_repository = invite_repository
        self.pos_auth_repository = pos_auth_repository
        self.transaction_repository = transaction_repository
        self.transaction_service = transaction_service
        self.bank_pos_service = bank_pos_service
        self.connection = connection

    async def get_session(self, *, principal: AuthPrincipal) -> MerchantSessionResponse:
        await self.user_repository.upsert_merchant_user(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
        )
        rows = await self.merchant_account_repository.list_visible_accounts(
            user_id=principal.user_id
        )
        return MerchantSessionResponse(
            user_id=principal.user_id,
            email=principal.email,
            display_name=principal.display_name,
            accounts=[self._account_response(row, row["effective_role"]) for row in rows],
        )

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
                mcc=payload.mcc,
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
            mcc=payload.mcc or parent["mcc"],
            subscription_tier=None,
        )
        return self._account_response(account, MembershipRole.ADMIN.value)

    async def configure_bank_profile(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
        payload: MerchantBankProfileUpsertRequest,
    ) -> MerchantBankProfileResponse:
        account = await self._get_manageable_account(
            principal=principal,
            account_id=account_id,
            minimum_role=MembershipRole.ADMIN.value,
        )
        if account["account_type"] != AccountType.POS.value:
            raise ValidationFailed("Bank profile can only be configured on a POS account.")
        profile = await self.bank_profile_repository.upsert_profile(
            merchant_account_id=account_id,
            provider=payload.provider,
            bank_user_id=payload.bank_user_id,
            terminal_identificator=payload.terminal_identificator,
        )
        return MerchantBankProfileResponse(
            merchant_account_id=profile["merchant_account_id"],
            provider=profile["provider"],
            bank_user_id=profile["bank_user_id"],
            terminal_identificator=profile["terminal_identificator"],
            active=profile["active"],
        )

    async def upsert_pos_credentials(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
        payload: PosCredentialsUpsertRequest,
    ) -> PosCredentialsResponse:
        if self.pos_auth_repository is None:
            raise ValidationFailed("POS credentials repository is not configured.")
        account = await self._get_manageable_account(
            principal=principal,
            account_id=account_id,
            minimum_role=MembershipRole.ADMIN.value,
        )
        if account["account_type"] != AccountType.POS.value:
            raise ValidationFailed("POS credentials can only be configured on a POS account.")
        username = normalize_pos_username(payload.username)
        salt_hex, password_hash = hash_pos_password(payload.password)
        try:
            row = await self.pos_auth_repository.upsert_credentials(
                merchant_account_id=account_id,
                username=username,
                password_hash=password_hash,
                password_salt=salt_hex,
                created_by_merchant_user_id=principal.user_id,
            )
        except asyncpg.UniqueViolationError as exc:
            raise ValidationFailed("POS username is already in use.") from exc
        return PosCredentialsResponse(
            merchant_account_id=row["merchant_account_id"],
            username=row["username"],
            active=row["active"],
        )

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
                invite_id=None,
                account_id=account_id,
                invited_email=payload.email,
                role=payload.role,
                token=None,
            )

        token = secrets.token_urlsafe(24)
        invite = await self.invite_repository.create(
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
            invite_id=invite["id"],
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

    async def revoke_invite(
        self,
        *,
        principal: AuthPrincipal,
        invite_id: UUID,
    ) -> RevokeInviteResponse:
        invite = await self.invite_repository.get_active_by_id(invite_id=invite_id)
        if invite is None:
            raise NotFound("Invite does not exist or is no longer active.")
        await self._get_manageable_account(
            principal=principal,
            account_id=invite["merchant_account_id"],
            minimum_role=MembershipRole.ADMIN.value,
        )
        await self.invite_repository.mark_revoked(invite_id=invite_id)
        return RevokeInviteResponse(status="revoked", invite_id=invite_id)

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
        if account["account_type"] != AccountType.POS.value:
            raise ValidationFailed("IPS merchant transaction must be created on a POS account.")
        bank_profile = await self.bank_profile_repository.get_by_account_id(
            merchant_account_id=account["id"]
        )
        bank_credit_transfer_identificator: str | None = None
        bank_provider: str | None = None
        if bank_profile is not None:
            if account["mcc"] is None:
                raise ValidationFailed(
                    "Merchant account is missing MCC required for IPS skeniraj bank integration."
                )
            sequence = await self.transaction_repository.next_bank_transaction_counter()
            bank_credit_transfer_identificator = build_credit_transfer_identificator(
                terminal_identificator=str(bank_profile["terminal_identificator"]),
                sequence=sequence,
            )
            bank_provider = str(bank_profile["provider"])
        return await self.transaction_service.create_pos_draft(
            merchant_account_id=account["id"],
            account_display_name=account["display_name"],
            payee_name=account["payee_name"],
            payee_address=account["payee_address"],
            payee_city=account["payee_city"],
            payee_account_number=account["payee_account_number"],
            mcc=account["mcc"],
            payload=payload,
            qr_kind="PT",
            bank_provider=bank_provider,
            bank_credit_transfer_identificator=bank_credit_transfer_identificator,
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

    async def sync_bank_transaction_status(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
        transaction_id: UUID,
    ) -> TransactionSummaryResponse:
        await self._get_manageable_account(
            principal=principal,
            account_id=account_id,
            minimum_role=MembershipRole.OPERATOR.value,
        )
        row = await self.bank_pos_service.sync_transaction_status(
            merchant_account_id=account_id,
            transaction_id=transaction_id,
        )
        return TransactionSummaryResponse(
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

    async def request_to_pay(
        self,
        *,
        principal: AuthPrincipal,
        account_id: UUID,
        payload: MerchantRequestToPayRequest,
    ) -> TransactionSummaryResponse:
        account = await self._get_manageable_account(
            principal=principal,
            account_id=account_id,
            minimum_role=MembershipRole.OPERATOR.value,
        )
        if account["payee_account_number"] is None:
            raise ValidationFailed("Merchant account is missing a payee account number.")
        if account["account_type"] != AccountType.POS.value:
            raise ValidationFailed("requestToPay can only run on a POS account.")

        bank_profile = await self.bank_profile_repository.get_by_account_id(
            merchant_account_id=account["id"]
        )
        if bank_profile is None:
            raise ValidationFailed("Merchant account must have a bank profile before requestToPay.")

        sequence = await self.transaction_repository.next_bank_transaction_counter()
        bank_credit_transfer_identificator = build_credit_transfer_identificator(
            terminal_identificator=str(bank_profile["terminal_identificator"]),
            sequence=sequence,
        )
        payment_ref = f"PLC-{secrets.token_hex(8).upper()}"

        row = await self.bank_pos_service.request_to_pay(
            merchant_account_id=account["id"],
            account_display_name=account["display_name"],
            payee_name=account["payee_name"],
            payee_address=account["payee_address"],
            payee_city=account["payee_city"],
            payee_account_number=account["payee_account_number"],
            bank_provider=str(bank_profile["provider"]),
            tid=str(bank_profile["terminal_identificator"]),
            credit_transfer_identificator=bank_credit_transfer_identificator,
            amount=payload.amount,
            debtor_account_number=payload.debtor_account_number,
            one_time_code=payload.one_time_code,
            debtor_reference=payload.debtor_reference,
            debtor_name=payload.debtor_name,
            debtor_address=payload.debtor_address,
            payment_purpose=payload.payment_purpose,
            payment_ref=payment_ref,
        )
        return TransactionSummaryResponse(
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
            mcc=row["mcc"],
            active=row["active"],
            effective_role=effective_role,
        )
