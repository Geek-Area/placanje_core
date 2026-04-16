from uuid import UUID

import pytest

from app.core.pos_security import hash_pos_password
from app.domain.auth import PosSessionPrincipal
from app.domain.models import (
    CreatePosTransactionRequest,
    MerchantTransactionCreateResponse,
    PosLoginRequest,
)
from app.services.pos import PosService


class FakePosAuthRepository:
    def __init__(self) -> None:
        salt_hex, password_hash = hash_pos_password("test1234")
        self.credentials = {
            "id": UUID("60000000-0000-0000-0000-000000000001"),
            "username": "pos1",
            "password_salt": salt_hex,
            "password_hash": password_hash,
            "credential_active": True,
            "merchant_account_id": UUID("70000000-0000-0000-0000-000000000001"),
            "merchant_account_active": True,
            "display_name": "POS 1",
            "account_type": "pos",
            "payee_name": "POS 1",
            "payee_account_number": "160000000000000000",
            "payee_address": "Bulevar Test 1",
            "payee_city": "Beograd",
            "mcc": "5411",
        }
        self.created_session = None
        self.active_session = {
            "session_id": UUID("80000000-0000-0000-0000-000000000001"),
            "merchant_pos_credential_id": self.credentials["id"],
            "username": "pos1",
            "merchant_account_id": self.credentials["merchant_account_id"],
            "credential_active": True,
            "merchant_account_active": True,
            "display_name": "POS 1",
            "account_type": "pos",
            "payee_name": "POS 1",
            "payee_account_number": "160000000000000000",
            "payee_address": "Bulevar Test 1",
            "payee_city": "Beograd",
            "mcc": "5411",
        }

    async def get_credentials_by_username(self, *, username):
        if username == "pos1":
            return self.credentials
        return None

    async def create_session(self, **kwargs):
        self.created_session = kwargs
        return kwargs

    async def touch_last_login(self, *, credential_id):
        return None

    async def get_active_session(self, *, session_token_hash):
        if self.created_session is None:
            return None
        return self.active_session

    async def touch_session(self, *, session_id):
        return None

    async def revoke_session(self, *, session_token_hash):
        return None


class FakeMerchantAccountRepository:
    async def get_account(self, *, account_id):
        return {
            "id": account_id,
            "account_type": "pos",
            "display_name": "POS 1",
            "payee_name": "POS 1",
            "payee_account_number": "160000000000000000",
            "payee_address": "Bulevar Test 1",
            "payee_city": "Beograd",
            "mcc": "5411",
        }


class FakeBankProfileRepository:
    async def get_by_account_id(self, *, merchant_account_id):
        return None


class FakeTransactionRepository:
    async def next_bank_transaction_counter(self):
        return 1

    async def list_account_transactions(self, *, merchant_account_id, limit, offset):
        return []

    async def account_stats(self, *, merchant_account_id):
        return {
            "total_transactions": 0,
            "completed_transactions": 0,
            "awaiting_payment_transactions": 0,
            "expired_transactions": 0,
            "total_completed_amount": 0,
        }


class FakeTransactionService:
    async def create_pos_draft(self, **kwargs):
        return MerchantTransactionCreateResponse(
            transaction_id=UUID("90000000-0000-0000-0000-000000000001"),
            payment_ref="PLC-TEST",
            status="awaiting_payment",
            qr_string="K:PT|V:01",
            bank_credit_transfer_identificator=None,
        )


class FakeBankPosService:
    async def sync_transaction_status(self, *, merchant_account_id, transaction_id):
        return {
            "id": transaction_id,
            "form_type": "ips",
            "status": "completed",
            "payment_ref": "PLC-TEST",
            "bank_provider": None,
            "bank_credit_transfer_identificator": None,
            "bank_status_code": "00",
            "bank_status_description": "executed",
            "amount": 450,
            "currency": "RSD",
            "payment_code": "221",
            "payment_description": "Test",
            "payee_name": "POS 1",
            "payee_account_number": "160000000000000000",
            "merchant_account_id": merchant_account_id,
            "reference_model": "97",
            "reference_number": "12345",
            "bank_transaction_ref": None,
            "completed_at": None,
            "created_at": None,
        }


def build_service() -> PosService:
    return PosService(
        pos_auth_repository=FakePosAuthRepository(),
        merchant_account_repository=FakeMerchantAccountRepository(),
        bank_profile_repository=FakeBankProfileRepository(),
        transaction_repository=FakeTransactionRepository(),
        transaction_service=FakeTransactionService(),
        bank_pos_service=FakeBankPosService(),
        session_ttl_hours=24,
    )


@pytest.mark.asyncio
async def test_pos_login_returns_session_token() -> None:
    service = build_service()

    result = await service.login(payload=PosLoginRequest(username="pos1", password="test1234"))

    assert result.username == "pos1"
    assert result.session_token != ""
    assert result.merchant_account.display_name == "POS 1"


@pytest.mark.asyncio
async def test_pos_create_transaction_uses_session_account() -> None:
    service = build_service()

    result = await service.create_pos_transaction(
        principal=PosSessionPrincipal(
            credential_id=UUID("60000000-0000-0000-0000-000000000001"),
            merchant_account_id=UUID("70000000-0000-0000-0000-000000000001"),
            username="pos1",
        ),
        payload=CreatePosTransactionRequest(
            amount="450.00",
            payment_description="Test payment",
            reference_model="97",
            reference_number="12345",
        ),
    )

    assert result.payment_ref == "PLC-TEST"
    assert result.status == "awaiting_payment"
