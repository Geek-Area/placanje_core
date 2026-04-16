from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

import httpx

from app.core.errors import NotFound, ValidationFailed


def _format_bank_credit_transfer_amount(amount: Decimal) -> str:
    return f"{amount:.2f}".replace(".", "")


def _extract_status_code(payload: dict[str, Any]) -> str:
    candidates = [
        payload.get("statusCode"),
        payload.get("status"),
        payload.get("code"),
    ]
    for candidate in candidates:
        if candidate is not None:
            normalized = str(candidate).strip()
            if normalized != "":
                return normalized
    raise ValidationFailed("Bank response is missing a status code.", details={"payload": payload})


def _extract_status_description(payload: dict[str, Any]) -> str | None:
    candidates = [
        payload.get("statusDescription"),
        payload.get("message"),
        payload.get("description"),
    ]
    for candidate in candidates:
        if candidate is not None:
            normalized = str(candidate).strip()
            if normalized != "":
                return normalized
    return None


def _extract_bank_transaction_ref(payload: dict[str, Any]) -> str | None:
    candidates = [
        payload.get("bankTransactionRef"),
        payload.get("transactionReference"),
        payload.get("reference"),
        payload.get("creditTransferIdentificator"),
    ]
    for candidate in candidates:
        if candidate is not None:
            normalized = str(candidate).strip()
            if normalized != "":
                return normalized
    return None


class BankProfileLookup(Protocol):
    async def get_by_account_id(self, *, merchant_account_id: UUID) -> Any: ...


class BankSessionTokenStore(Protocol):
    async def get_active_for_profile(self, *, merchant_bank_profile_id: UUID) -> Any: ...

    async def upsert_for_profile(
        self,
        *,
        merchant_bank_profile_id: UUID,
        session_token: str,
        expires_at: datetime,
    ) -> Any: ...


class BankTransactionStore(Protocol):
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
    ) -> Any: ...

    async def get_account_transaction(
        self,
        *,
        merchant_account_id: UUID,
        transaction_id: UUID,
    ) -> Any: ...

    async def update_bank_status(
        self,
        *,
        transaction_id: UUID,
        bank_status_code: str,
        bank_status_description: str | None,
        checked_at: datetime,
    ) -> str: ...

    async def mark_transaction_completed(
        self,
        *,
        transaction_id: UUID,
        bank_transaction_ref: str,
        completed_at: datetime,
        bank_status_code: str,
        bank_status_description: str | None,
    ) -> str: ...

    async def mark_transaction_failed(
        self,
        *,
        transaction_id: UUID,
        bank_status_code: str,
        bank_status_description: str | None,
    ) -> str: ...


@dataclass(slots=True)
class BankStatusResult:
    status_code: str
    status_description: str | None
    raw_response: dict[str, Any]


class BancaIntesaPosClient:
    def __init__(self, *, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def generate_token(self, *, bank_user_id: str, tid: str) -> tuple[str, datetime]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/res/v2/generateToken",
                    json={"userId": bank_user_id, "tid": tid},
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValidationFailed(f"Bank token generation failed: {exc}") from exc
        payload = response.json()
        session_token = str(payload["sessionToken"])
        token_expiry_time = int(payload["tokenExpiryTime"])
        expires_at = datetime.now(tz=UTC) + timedelta(minutes=token_expiry_time)
        return session_token, expires_at

    async def check_credit_transfer_status(
        self,
        *,
        session_token: str,
        tid: str,
        credit_transfer_identificator: str,
        amount: Decimal,
    ) -> BankStatusResult:
        request_payload = {
            "creditTransferIdentificator": credit_transfer_identificator,
            "terminalIdentificator": tid,
            "creditTransferAmount": _format_bank_credit_transfer_amount(amount),
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/ips/v2/checkCTStatus",
                    headers={
                        "Authorization": f"Bearer {session_token}",
                        "Terminal-Identification": tid,
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValidationFailed(f"Bank status sync failed: {exc}") from exc
        payload = response.json()
        return BankStatusResult(
            status_code=_extract_status_code(payload),
            status_description=_extract_status_description(payload),
            raw_response=payload,
        )

    async def request_to_pay(
        self,
        *,
        session_token: str,
        tid: str,
        credit_transfer_identificator: str,
        amount: Decimal,
        debtor_account_number: str,
        one_time_code: str | None,
        debtor_reference: str | None,
        debtor_name: str | None,
        debtor_address: str | None,
        payment_purpose: str | None,
    ) -> BankStatusResult:
        request_payload: dict[str, Any] = {
            "creditTransferIdentificator": credit_transfer_identificator,
            "terminalIdentificator": tid,
            "creditTransferAmount": _format_bank_credit_transfer_amount(amount),
            "creditTransferAmountCurrency": "941",
            "debtorAccountNumber": debtor_account_number,
        }
        if one_time_code:
            request_payload["oneTimeCode"] = one_time_code
        if debtor_reference:
            request_payload["debtorReference"] = debtor_reference
        if debtor_name:
            request_payload["debtorName"] = debtor_name
        if debtor_address:
            request_payload["debtorAddress"] = debtor_address
        if payment_purpose:
            request_payload["paymentPurpose"] = payment_purpose

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/ips/v2/requestToPay/",
                    headers={
                        "Authorization": f"Bearer {session_token}",
                        "Terminal-Identification": tid,
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValidationFailed(f"Bank requestToPay failed: {exc}") from exc
        payload = response.json()
        return BankStatusResult(
            status_code=_extract_status_code(payload),
            status_description=_extract_status_description(payload),
            raw_response=payload,
        )


class BankPosService:
    def __init__(
        self,
        *,
        bank_profile_repository: BankProfileLookup,
        bank_session_repository: BankSessionTokenStore,
        transaction_repository: BankTransactionStore,
        client: BancaIntesaPosClient,
    ) -> None:
        self.bank_profile_repository = bank_profile_repository
        self.bank_session_repository = bank_session_repository
        self.transaction_repository = transaction_repository
        self.client = client

    async def sync_transaction_status(
        self,
        *,
        merchant_account_id: UUID,
        transaction_id: UUID,
    ) -> Any:
        bank_profile = await self.bank_profile_repository.get_by_account_id(
            merchant_account_id=merchant_account_id
        )
        if bank_profile is None:
            raise NotFound("Merchant account does not have a bank profile configured.")

        transaction = await self.transaction_repository.get_account_transaction(
            merchant_account_id=merchant_account_id,
            transaction_id=transaction_id,
        )
        if transaction is None:
            raise NotFound("Transaction does not exist for this merchant account.")
        if transaction["bank_credit_transfer_identificator"] is None:
            raise ValidationFailed("Transaction is missing the bank credit transfer identificator.")

        session_token = await self._get_session_token(bank_profile=bank_profile)
        result = await self.client.check_credit_transfer_status(
            session_token=session_token,
            tid=str(bank_profile["terminal_identificator"]),
            credit_transfer_identificator=str(transaction["bank_credit_transfer_identificator"]),
            amount=transaction["amount"],
        )

        if result.status_code == "00":
            await self.transaction_repository.mark_transaction_completed(
                transaction_id=transaction_id,
                bank_transaction_ref=str(
                    result.raw_response.get("bankTransactionRef")
                    or transaction["bank_credit_transfer_identificator"]
                ),
                completed_at=datetime.now(tz=UTC),
                bank_status_code=result.status_code,
                bank_status_description=result.status_description,
            )
        elif result.status_code == "05":
            await self.transaction_repository.mark_transaction_failed(
                transaction_id=transaction_id,
                bank_status_code=result.status_code,
                bank_status_description=result.status_description,
            )
        else:
            await self.transaction_repository.update_bank_status(
                transaction_id=transaction_id,
                bank_status_code=result.status_code,
                bank_status_description=result.status_description,
                checked_at=datetime.now(tz=UTC),
            )

        return await self.transaction_repository.get_account_transaction(
            merchant_account_id=merchant_account_id,
            transaction_id=transaction_id,
        )

    async def request_to_pay(
        self,
        *,
        merchant_account_id: UUID,
        account_display_name: str,
        payee_name: str,
        payee_address: str | None,
        payee_city: str | None,
        payee_account_number: str,
        bank_provider: str,
        tid: str,
        credit_transfer_identificator: str,
        amount: Decimal,
        debtor_account_number: str,
        one_time_code: str | None,
        debtor_reference: str | None,
        debtor_name: str | None,
        debtor_address: str | None,
        payment_purpose: str | None,
        payment_ref: str,
    ) -> Any:
        bank_profile = await self.bank_profile_repository.get_by_account_id(
            merchant_account_id=merchant_account_id
        )
        if bank_profile is None:
            raise NotFound("Merchant account does not have a bank profile configured.")

        created = await self.transaction_repository.create_request_to_pay(
            merchant_account_id=merchant_account_id,
            account_display_name=account_display_name,
            payee_name=payee_name,
            payee_address=payee_address,
            payee_city=payee_city,
            payee_account_number=payee_account_number,
            payer_name=debtor_name,
            payer_address=debtor_address,
            payer_city=None,
            amount=amount,
            payment_description=payment_purpose,
            payment_ref=payment_ref,
            payment_code="221",
            bank_provider=bank_provider,
            bank_credit_transfer_identificator=credit_transfer_identificator,
        )

        session_token = await self._get_session_token(bank_profile=bank_profile)
        result = await self.client.request_to_pay(
            session_token=session_token,
            tid=tid,
            credit_transfer_identificator=credit_transfer_identificator,
            amount=amount,
            debtor_account_number=debtor_account_number,
            one_time_code=one_time_code,
            debtor_reference=debtor_reference,
            debtor_name=debtor_name,
            debtor_address=debtor_address,
            payment_purpose=payment_purpose,
        )

        if result.status_code == "00":
            await self.transaction_repository.mark_transaction_completed(
                transaction_id=created["id"],
                bank_transaction_ref=_extract_bank_transaction_ref(result.raw_response)
                or credit_transfer_identificator,
                completed_at=datetime.now(tz=UTC),
                bank_status_code=result.status_code,
                bank_status_description=result.status_description,
            )
        else:
            await self.transaction_repository.mark_transaction_failed(
                transaction_id=created["id"],
                bank_status_code=result.status_code,
                bank_status_description=result.status_description,
            )

        return await self.transaction_repository.get_account_transaction(
            merchant_account_id=merchant_account_id,
            transaction_id=created["id"],
        )

    async def _get_session_token(self, *, bank_profile: Any) -> str:
        existing = await self.bank_session_repository.get_active_for_profile(
            merchant_bank_profile_id=bank_profile["id"]
        )
        if existing is not None:
            return str(existing["session_token"])

        session_token, expires_at = await self.client.generate_token(
            bank_user_id=str(bank_profile["bank_user_id"]),
            tid=str(bank_profile["terminal_identificator"]),
        )
        await self.bank_session_repository.upsert_for_profile(
            merchant_bank_profile_id=bank_profile["id"],
            session_token=session_token,
            expires_at=expires_at,
        )
        return session_token
