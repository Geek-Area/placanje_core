from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.errors import Unauthorized, ValidationFailed
from app.core.pos_security import (
    hash_pos_session_token,
    issue_pos_session_token,
    normalize_pos_username,
    verify_pos_password,
)
from app.domain.auth import PosSessionPrincipal
from app.domain.bank_pos import build_credit_transfer_identificator
from app.domain.models import (
    CreatePosTransactionRequest,
    LogoutResponse,
    MerchantAccountStatsResponse,
    MerchantTransactionCreateResponse,
    PosAccountContextResponse,
    PosLoginRequest,
    PosLoginResponse,
    PosSessionResponse,
    TransactionListResponse,
    TransactionSummaryResponse,
)


class PosService:
    def __init__(
        self,
        *,
        pos_auth_repository: Any,
        merchant_account_repository: Any,
        bank_profile_repository: Any,
        transaction_repository: Any,
        transaction_service: Any,
        bank_pos_service: Any,
        session_ttl_hours: int,
    ) -> None:
        self.pos_auth_repository = pos_auth_repository
        self.merchant_account_repository = merchant_account_repository
        self.bank_profile_repository = bank_profile_repository
        self.transaction_repository = transaction_repository
        self.transaction_service = transaction_service
        self.bank_pos_service = bank_pos_service
        self.session_ttl_hours = session_ttl_hours

    async def login(self, *, payload: PosLoginRequest) -> PosLoginResponse:
        username = normalize_pos_username(payload.username)
        credentials = await self.pos_auth_repository.get_credentials_by_username(username=username)
        if credentials is None:
            raise Unauthorized("POS username or password is invalid.")
        if not credentials["credential_active"] or not credentials["merchant_account_active"]:
            raise Unauthorized("POS username or password is invalid.")
        if credentials["account_type"] != "pos":
            raise Unauthorized("POS username or password is invalid.")
        password_valid = verify_pos_password(
            password=payload.password,
            salt_hex=str(credentials["password_salt"]),
            expected_hash_hex=str(credentials["password_hash"]),
        )
        if not password_valid:
            raise Unauthorized("POS username or password is invalid.")

        session_token = issue_pos_session_token()
        expires_at = datetime.now(tz=UTC) + timedelta(hours=self.session_ttl_hours)
        await self.pos_auth_repository.create_session(
            merchant_pos_credential_id=credentials["id"],
            session_token_hash=hash_pos_session_token(session_token),
            expires_at=expires_at,
        )
        await self.pos_auth_repository.touch_last_login(credential_id=credentials["id"])
        return PosLoginResponse(
            session_token=session_token,
            expires_at=expires_at,
            username=str(credentials["username"]),
            merchant_account=self._account_context(credentials),
        )

    async def resolve_session(self, *, session_token: str) -> PosSessionPrincipal:
        row = await self.pos_auth_repository.get_active_session(
            session_token_hash=hash_pos_session_token(session_token)
        )
        if row is None:
            raise Unauthorized("POS session is invalid or expired.")
        if not row["credential_active"] or not row["merchant_account_active"]:
            raise Unauthorized("POS session is invalid or expired.")
        await self.pos_auth_repository.touch_session(session_id=row["session_id"])
        return PosSessionPrincipal(
            credential_id=row["merchant_pos_credential_id"],
            merchant_account_id=row["merchant_account_id"],
            username=str(row["username"]),
        )

    async def get_session(self, *, principal: PosSessionPrincipal) -> PosSessionResponse:
        account = await self.merchant_account_repository.get_account(
            account_id=principal.merchant_account_id
        )
        if account is None or account["account_type"] != "pos":
            raise Unauthorized("POS session is invalid or expired.")
        return PosSessionResponse(
            username=principal.username,
            merchant_account=self._account_context(account),
        )

    async def logout(self, *, session_token: str) -> LogoutResponse:
        await self.pos_auth_repository.revoke_session(
            session_token_hash=hash_pos_session_token(session_token)
        )
        return LogoutResponse(status="revoked", scope="current_pos_session")

    async def create_pos_transaction(
        self,
        *,
        principal: PosSessionPrincipal,
        payload: CreatePosTransactionRequest,
    ) -> MerchantTransactionCreateResponse:
        account = await self.merchant_account_repository.get_account(
            account_id=principal.merchant_account_id
        )
        if account is None or account["account_type"] != "pos":
            raise Unauthorized("POS session is invalid or expired.")
        if account["payee_account_number"] is None:
            raise ValidationFailed("Merchant account is missing a payee account number.")

        bank_profile = await self.bank_profile_repository.get_by_account_id(
            merchant_account_id=principal.merchant_account_id
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
            merchant_account_id=principal.merchant_account_id,
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

    async def list_transactions(
        self,
        *,
        principal: PosSessionPrincipal,
        limit: int,
        offset: int,
    ) -> TransactionListResponse:
        rows = await self.transaction_repository.list_account_transactions(
            merchant_account_id=principal.merchant_account_id,
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

    async def get_stats(self, *, principal: PosSessionPrincipal) -> MerchantAccountStatsResponse:
        stats = await self.transaction_repository.account_stats(
            merchant_account_id=principal.merchant_account_id
        )
        return MerchantAccountStatsResponse(
            account_id=principal.merchant_account_id,
            total_transactions=stats["total_transactions"],
            completed_transactions=stats["completed_transactions"],
            awaiting_payment_transactions=stats["awaiting_payment_transactions"],
            expired_transactions=stats["expired_transactions"],
            total_completed_amount=stats["total_completed_amount"],
        )

    async def sync_bank_transaction_status(
        self,
        *,
        principal: PosSessionPrincipal,
        transaction_id: UUID,
    ) -> TransactionSummaryResponse:
        row = await self.bank_pos_service.sync_transaction_status(
            merchant_account_id=principal.merchant_account_id,
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

    @staticmethod
    def _account_context(row: Any) -> PosAccountContextResponse:
        return PosAccountContextResponse(
            id=row["merchant_account_id"] if "merchant_account_id" in row else row["id"],
            account_type=row["account_type"],
            display_name=row["display_name"],
            payee_name=row["payee_name"],
            payee_account_number=row["payee_account_number"],
            payee_address=row["payee_address"],
            payee_city=row["payee_city"],
            mcc=row["mcc"],
        )
