from uuid import UUID, uuid4

import pytest

from app.domain.auth import AuthPrincipal
from app.domain.models import MerchantInviteRequest, MerchantSignupRequest
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
            "account_type": "organization",
            "slug": "org",
            "display_name": "Org",
            "payee_name": "Org",
            "payee_account_number": "340000000000000001",
            "payee_address": None,
            "payee_city": None,
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
        return kwargs

    async def get_active_by_token(self, *, token):
        return self.active_invite

    async def mark_accepted(self, *, invite_id):
        return None


class FakeTransactionRepository:
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
        invite_repository=FakeInviteRepository(),
        transaction_repository=FakeTransactionRepository(),
        transaction_service=FakeTransactionService(),
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
        invite_repository=invite_repository,
        transaction_repository=FakeTransactionRepository(),
        transaction_service=FakeTransactionService(),
        connection=FakeConnection(),
    )

    result = await service.invite_cashier(
        principal=principal,
        account_id=UUID("40000000-0000-0000-0000-000000000001"),
        payload=MerchantInviteRequest(email="cashier@example.com", role="operator"),
    )

    assert result.invitation_mode == "token"
    assert result.token is not None
