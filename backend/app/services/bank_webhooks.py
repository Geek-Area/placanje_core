import hashlib
import hmac
import json
from typing import Protocol

from app.core.errors import Unauthorized, ValidationFailed
from app.domain.enums import TransactionStatus
from app.domain.models import BankWebhookStatusPayload


class TransactionStatusUpdater(Protocol):
    async def mark_payment_completed(
        self,
        *,
        payment_ref: str,
        bank_transaction_ref: str,
        completed_at: str,
    ) -> str: ...


class BankWebhookService:
    def __init__(
        self,
        *,
        transaction_repository: TransactionStatusUpdater,
        secret: str | None,
    ) -> None:
        self.transaction_repository = transaction_repository
        self.secret = secret

    async def process_status_update(
        self,
        *,
        provider: str,
        payload: BankWebhookStatusPayload,
        signature: str,
    ) -> None:
        if self.secret is None:
            raise Unauthorized("Bank webhook secret is not configured.")
        self._verify_signature(provider=provider, payload=payload, signature=signature)
        if payload.status != TransactionStatus.COMPLETED.value:
            raise ValidationFailed(
                "Unsupported bank webhook status.",
                details={"status": payload.status},
            )
        await self.transaction_repository.mark_payment_completed(
            payment_ref=payload.payment_ref,
            bank_transaction_ref=payload.bank_transaction_ref,
            completed_at=payload.completed_at.isoformat(),
        )

    def _verify_signature(
        self,
        *,
        provider: str,
        payload: BankWebhookStatusPayload,
        signature: str,
    ) -> None:
        secret = self.secret
        if secret is None:
            raise Unauthorized("Bank webhook secret is not configured.")
        canonical_payload = json.dumps(
            {
                "provider": provider,
                "payment_ref": payload.payment_ref,
                "bank_transaction_ref": payload.bank_transaction_ref,
                "status": payload.status,
                "amount": str(payload.amount),
                "completed_at": payload.completed_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            canonical_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            raise Unauthorized("Invalid bank webhook signature.")
