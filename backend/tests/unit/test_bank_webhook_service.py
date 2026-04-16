import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.errors import Unauthorized, ValidationFailed
from app.domain.models import BankWebhookStatusPayload
from app.services.bank_webhooks import BankWebhookService


class FakeTransactionStatusRepository:
    def __init__(self) -> None:
        self.called_with: dict[str, str] | None = None

    async def mark_payment_completed(
        self,
        *,
        payment_ref: str,
        bank_transaction_ref: str,
        completed_at: str,
    ) -> str:
        self.called_with = {
            "payment_ref": payment_ref,
            "bank_transaction_ref": bank_transaction_ref,
            "completed_at": completed_at,
        }
        return "UPDATE 1"


def _build_signature(secret: str, payload: BankWebhookStatusPayload, provider: str) -> str:
    body = json.dumps(
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
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_bank_webhook_service_updates_transaction_on_valid_signature() -> None:
    repository = FakeTransactionStatusRepository()
    service = BankWebhookService(transaction_repository=repository, secret="top-secret")
    payload = BankWebhookStatusPayload(
        payment_ref="PLC-123",
        bank_transaction_ref="BANK-123",
        status="completed",
        amount=Decimal("1250.00"),
        completed_at=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )

    await service.process_status_update(
        provider="demo-bank",
        payload=payload,
        signature=_build_signature("top-secret", payload, "demo-bank"),
    )

    assert repository.called_with is not None
    assert repository.called_with["payment_ref"] == "PLC-123"


@pytest.mark.asyncio
async def test_bank_webhook_service_rejects_invalid_signature() -> None:
    repository = FakeTransactionStatusRepository()
    service = BankWebhookService(transaction_repository=repository, secret="top-secret")
    payload = BankWebhookStatusPayload(
        payment_ref="PLC-123",
        bank_transaction_ref="BANK-123",
        status="completed",
        amount=Decimal("1250.00"),
        completed_at=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(Unauthorized):
        await service.process_status_update(
            provider="demo-bank",
            payload=payload,
            signature="invalid",
        )


@pytest.mark.asyncio
async def test_bank_webhook_service_rejects_unsupported_status() -> None:
    repository = FakeTransactionStatusRepository()
    service = BankWebhookService(transaction_repository=repository, secret="top-secret")
    payload = BankWebhookStatusPayload(
        payment_ref="PLC-123",
        bank_transaction_ref="BANK-123",
        status="failed",
        amount=Decimal("1250.00"),
        completed_at=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(ValidationFailed):
        await service.process_status_update(
            provider="demo-bank",
            payload=payload,
            signature=_build_signature("top-secret", payload, "demo-bank"),
        )
