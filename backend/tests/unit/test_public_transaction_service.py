from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain.models import CreatePublicTransactionRequest
from app.services.transactions import PublicTransactionService


class FakeTransactionContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def transaction(self) -> FakeTransactionContext:
        return FakeTransactionContext()


class FakeTransactionRepository:
    async def create_regular(self, *, payload, qr_string, payment_ref, consumer_user_id):
        return {
            "id": UUID("30000000-0000-0000-0000-000000000001"),
            "created_at": datetime.now(tz=UTC),
            "payload": payload,
            "qr_string": qr_string,
            "payment_ref": payment_ref,
            "status": "draft",
            "consumer_user_id": consumer_user_id,
        }

    async def create_pos_draft(self, **kwargs):
        return {
            "id": UUID("30000000-0000-0000-0000-000000000001"),
            "created_at": datetime.now(tz=UTC),
            "payment_ref": kwargs["payment_ref"],
            "bank_credit_transfer_identificator": kwargs["bank_credit_transfer_identificator"],
            "status": "awaiting_payment",
        }

    async def get_public_share_payload(self, *, slug):
        if slug != "known-slug":
            return None
        return {
            "transaction_id": UUID("30000000-0000-0000-0000-000000000001"),
            "payment_ref": "PLC-123",
            "form_type": "regular",
            "status": "draft",
            "payer_name": "Petar Petrovic",
            "payer_address": None,
            "payer_city": None,
            "payee_name": "Mina Minic",
            "payee_address": "Njegoseva 1",
            "payee_city": "Nis",
            "payee_account_number": "340000000000000001",
            "amount": Decimal("1500.00"),
            "currency": "RSD",
            "payment_code": "289",
            "reference_model": "97",
            "reference_number": "12345",
            "payment_description": "Rucak",
            "qr_string": "K:PR|V:01",
            "expires_at": datetime(2099, 1, 1, tzinfo=UTC),
            "revoked_at": None,
        }


class FakeShareLinkRepository:
    async def create(self, *, transaction_id, slug, qr_string, expires_at):
        return {"slug": slug, "expires_at": expires_at}

    async def increment_access_count(self, *, slug):
        return None


@pytest.mark.asyncio
async def test_public_transaction_service_creates_share_response() -> None:
    service = PublicTransactionService(
        transaction_repository=FakeTransactionRepository(),
        share_link_repository=FakeShareLinkRepository(),
        connection=FakeConnection(),
        base_url="http://localhost:8000",
        share_link_ttl_days=30,
    )
    payload = CreatePublicTransactionRequest(
        payee_name="Mina Minic",
        payee_address="Njegoseva 1",
        payee_city="Nis",
        payee_account_number="340000000000000001",
        amount=Decimal("1500"),
        payment_description="Rucak",
        reference_model="97",
        reference_number="12345",
    )

    result = await service.create_public_regular(payload)

    assert str(result.transaction_id) == "30000000-0000-0000-0000-000000000001"
    assert result.share_url.startswith("http://localhost:8000/v1/public/share/")
    assert "K:PR|V:01|C:1" in result.qr_string
    assert result.status == "draft"


@pytest.mark.asyncio
async def test_public_transaction_service_returns_share_details() -> None:
    service = PublicTransactionService(
        transaction_repository=FakeTransactionRepository(),
        share_link_repository=FakeShareLinkRepository(),
        connection=FakeConnection(),
        base_url="http://localhost:8000",
        share_link_ttl_days=30,
    )

    result = await service.get_public_share(slug="known-slug")

    assert result.payee_name == "Mina Minic"
    assert result.payment_description == "Rucak"
    assert result.payment_ref == "PLC-123"
