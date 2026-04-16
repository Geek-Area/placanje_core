from decimal import Decimal
from uuid import UUID

import pytest

from app.domain.models import CreatePosTransactionRequest
from app.repositories.transactions import TransactionRepository


class FakeConnection:
    def __init__(self) -> None:
        self.query: str | None = None
        self.args: tuple[object, ...] | None = None

    async def fetchrow(self, query: str, *args: object) -> dict[str, object]:
        self.query = query
        self.args = args
        return {
            "id": UUID("40000000-0000-0000-0000-000000000099"),
            "created_at": None,
            "status": "awaiting_payment",
            "payment_ref": "PLC-TEST",
        }


@pytest.mark.asyncio
async def test_create_pos_draft_casts_metadata_value_to_text() -> None:
    connection = FakeConnection()
    repository = TransactionRepository(connection=connection)  # type: ignore[arg-type]

    await repository.create_pos_draft(
        merchant_account_id=UUID("40000000-0000-0000-0000-000000000001"),
        account_display_name="Maxi POS",
        payee_name="Maxi POS",
        payee_address="Makenzijeva 2",
        payee_city="Belgrade",
        payee_account_number="340000000000000001",
        payload=CreatePosTransactionRequest(
            amount=Decimal("450.00"),
            payment_description="Test payment",
            reference_model="97",
            reference_number="12345",
        ),
        qr_string="K:PR|V:01",
        payment_ref="PLC-TEST",
    )

    assert connection.query is not None
    assert "jsonb_build_object('merchant_account_display_name', $16::text)" in connection.query
