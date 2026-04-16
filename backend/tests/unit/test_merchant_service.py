from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.auth import AuthPrincipal
from app.domain.models import (
    MerchantInviteRequest,
    MerchantRequestToPayRequest,
    MerchantSignupRequest,
    PosCredentialsUpsertRequest,
)
from app.services.merchant import MerchantService


class FakeTransactionContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def transaction(self) -> FakeTransactionContext:
        return FakeTransactionContext()


class FakeUserRepository:
    def __init__(self) -> None:
        self.merchant_lookup = None

    async def upsert_merchant_user(self, *, user_id, email, display_name):
        return {"id": user_id, "email": email, "display_name": display_name}

    async def get_merchant_user_by_email(self, *, email):
        return self.merchant_lookup


class FakeMerchantAccountRepository:
    def __init__(self) -> None:
        self.memberships = []
        self.account_type = "organization"

    async def create_account(self, **kwargs):
        return {
            "id": UUID("40000000-0000-0000-0000-000000000001"),
            "parent_account_id": kwargs["parent_account_id"],
            "account_type": kwargs["account_type"],
            "slug": kwargs["slug"],
            "display_name": kwargs["display_name"],
            "payee_name": kwargs["payee_name"],
            "payee_account_number": kwargs["payee_account_number"],
            "payee_address": kwargs["payee_address"],
            "payee_city": kwargs["payee_city"],
            "mcc": kwargs.get("mcc"),
            "active": True,
        }

    async def create_membership(self, **kwargs):
        self.memberships.append(kwargs)
        return kwargs

    async def list_visible_accounts(self, *, user_id):
        return []

    async def list_account_transactions_allowed(self, *, user_id, account_id):
        return True

    async def get_account(self, *, account_id):
        return {
            "id": account_id,
            "parent_account_id": None,
            "account_type": self.account_type,
            "slug": "org",
            "display_name": "Org",
            "payee_name": "Org",
            "payee_account_number": "340000000000000001",
            "payee_address": None,
            "payee_city": None,
            "mcc": None,
            "active": True,
        }

    async def get_effective_role(self, *, user_id, account_id):
        return "owner"


class FakeInviteRepository:
    def __init__(self) -> None:
        self.created = None
        self.active_invite = None

    async def create(self, **kwargs):
        self.created = kwargs
        return {"id": UUID("40000000-0000-0000-0000-0000000000AA"), **kwargs}

    async def get_active_by_token(self, *, token):
        return self.active_invite

    async def get_active_by_id(self, *, invite_id):
        return self.active_invite

    async def mark_accepted(self, *, invite_id):
        return None

    async def mark_revoked(self, *, invite_id):
        return None


class FakeBankProfileRepository:
    def __init__(self) -> None:
        self.profile = None

    async def get_by_account_id(self, *, merchant_account_id):
        return self.profile

    async def upsert_profile(self, **kwargs):
        return {
            "merchant_account_id": kwargs["merchant_account_id"],
            "provider": kwargs["provider"],
            "bank_user_id": kwargs["bank_user_id"],
            "terminal_identificator": kwargs["terminal_identificator"],
            "active": True,
        }


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
        return None


class FakeBankPosService:
    def __init__(self) -> None:
        self.request_to_pay_payload = None

    async def sync_transaction_status(self, *, merchant_account_id, transaction_id):
        return None

    async def request_to_pay(self, **kwargs):
        self.request_to_pay_payload = kwargs
        return {
            "id": UUID("50000000-0000-0000-0000-000000000001"),
            "form_type": "ips",
            "status": "completed",
            "payment_ref": kwargs["payment_ref"],
            "bank_provider": kwargs["bank_provider"],
            "bank_credit_transfer_identificator": kwargs["credit_transfer_identificator"],
            "bank_status_code": "00",
            "bank_status_description": "executed",
            "amount": kwargs["amount"],
            "currency": "RSD",
            "payment_code": "221",
            "payment_description": kwargs["payment_purpose"],
            "payee_name": kwargs["payee_name"],
            "payee_account_number": kwargs["payee_account_number"],
            "merchant_account_id": kwargs["merchant_account_id"],
            "reference_model": None,
            "reference_number": None,
            "bank_transaction_ref": kwargs["credit_transfer_identificator"],
            "completed_at": None,
            "created_at": datetime.now(tz=UTC),
        }


class FakePosAuthRepository:
    def __init__(self) -> None:
        self.saved = None

    async def upsert_credentials(self, **kwargs):
        self.saved = kwargs
        return {
            "merchant_account_id": kwargs["merchant_account_id"],
            "username": kwargs["username"],
            "active": True,
        }


def _principal() -> AuthPrincipal:
    return AuthPrincipal(
        user_id=uuid4(),
        email="owner@example.com",
        display_name="Owner",
        raw_claims={},
    )


@pytest.mark.asyncio
async def test_signup_owner_creates_owner_membership() -> None:
    user_repository = FakeUserRepository()
    merchant_account_repository = FakeMerchantAccountRepository()
    service = MerchantService(
        user_repository=user_repository,
        merchant_account_repository=merchant_account_repository,
        bank_profile_repository=FakeBankProfileRepository(),
        invite_repository=FakeInviteRepository(),
        transaction_repository=FakeTransactionRepository(),
        transaction_service=FakeTransactionService(),
        bank_pos_service=FakeBankPosService(),
        connection=FakeConnection(),
    )

    result = await service.signup_owner(
        principal=_principal(),
        payload=MerchantSignupRequest(
            display_name="Maxi",
            payee_account_number="340000000000000001",
        ),
    )

    assert result.account_type == "organization"
    assert merchant_account_repository.memberships[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_invite_cashier_returns_token_for_new_user() -> None:
    principal = _principal()
    invite_repository = FakeInviteRepository()
    service = MerchantService(
        user_repository=FakeUserRepository(),
        merchant_account_repository=FakeMerchantAccountRepository(),
        bank_profile_repository=FakeBankProfileRepository(),
        invite_repository=invite_repository,
        transaction_repository=FakeTransactionRepository(),
        transaction_service=FakeTransactionService(),
        bank_pos_service=FakeBankPosService(),
        connection=FakeConnection(),
    )

    result = await service.invite_cashier(
        principal=principal,
        account_id=UUID("40000000-0000-0000-0000-000000000001"),
        payload=MerchantInviteRequest(email="cashier@example.com", role="operator"),
    )

    assert result.invitation_mode == "token"
    assert result.token is not None


@pytest.mark.asyncio
async def test_request_to_pay_uses_bank_profile_for_selected_pos() -> None:
    bank_profile_repository = FakeBankProfileRepository()
    bank_profile_repository.profile = {
        "provider": "banca_intesa",
        "terminal_identificator": "TID12345",
    }
    bank_pos_service = FakeBankPosService()
    merchant_account_repository = FakeMerchantAccountRepository()
    merchant_account_repository.account_type = "pos"
    service = MerchantService(
        user_repository=FakeUserRepository(),
        merchant_account_repository=merchant_account_repository,
        bank_profile_repository=bank_profile_repository,
        invite_repository=FakeInviteRepository(),
        transaction_repository=FakeTransactionRepository(),
        transaction_service=FakeTransactionService(),
        bank_pos_service=bank_pos_service,
        connection=FakeConnection(),
    )

    result = await service.request_to_pay(
        principal=_principal(),
        account_id=UUID("40000000-0000-0000-0000-000000000001"),
        payload=MerchantRequestToPayRequest(
            amount="450.00",
            debtor_account_number="340000000000000001",
            one_time_code="123456",
            debtor_name="Petar Petrovic",
            debtor_address="Nemanjina 1",
            payment_purpose="Racun 15",
        ),
    )

    assert result.status == "completed"
    assert bank_pos_service.request_to_pay_payload is not None
    assert bank_pos_service.request_to_pay_payload["tid"] == "TID12345"
    assert bank_pos_service.request_to_pay_payload["bank_provider"] == "banca_intesa"


@pytest.mark.asyncio
async def test_upsert_pos_credentials_saves_normalized_username() -> None:
    merchant_account_repository = FakeMerchantAccountRepository()
    merchant_account_repository.account_type = "pos"
    pos_auth_repository = FakePosAuthRepository()
    service = MerchantService(
        user_repository=FakeUserRepository(),
        merchant_account_repository=merchant_account_repository,
        bank_profile_repository=FakeBankProfileRepository(),
        invite_repository=FakeInviteRepository(),
        transaction_repository=FakeTransactionRepository(),
        transaction_service=FakeTransactionService(),
        bank_pos_service=FakeBankPosService(),
        connection=FakeConnection(),
        pos_auth_repository=pos_auth_repository,
    )

    result = await service.upsert_pos_credentials(
        principal=_principal(),
        account_id=UUID("40000000-0000-0000-0000-000000000001"),
        payload=PosCredentialsUpsertRequest(username=" POS1 ", password="test1234"),
    )

    assert result.username == "pos1"
    assert pos_auth_repository.saved is not None
    assert pos_auth_repository.saved["username"] == "pos1"
