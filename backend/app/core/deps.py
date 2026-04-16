from collections.abc import AsyncIterator

import asyncpg
from fastapi import Depends

from app.core.auth import decode_access_token, require_bearer_token
from app.core.config import Settings, get_settings
from app.core.db import get_connection
from app.domain.auth import AuthPrincipal, PosSessionPrincipal
from app.repositories.bank_profiles import BankSessionTokenRepository, MerchantBankProfileRepository
from app.repositories.invites import PendingInviteRepository
from app.repositories.merchant_accounts import MerchantAccountRepository
from app.repositories.pos_auth import MerchantPosAuthRepository
from app.repositories.share_links import ShareLinkRepository
from app.repositories.subscriptions import SubscriptionRepository
from app.repositories.transactions import TransactionRepository
from app.repositories.users import UserRepository
from app.services.auth_sessions import AuthSessionService
from app.services.bank_pos import BancaIntesaPosClient, BankPosService
from app.services.bank_webhooks import BankWebhookService
from app.services.consumer import ConsumerService
from app.services.merchant import MerchantService
from app.services.pos import PosService
from app.services.subscriptions import SubscriptionService
from app.services.transactions import PublicTransactionService


def get_app_settings() -> Settings:
    return get_settings()


def get_current_principal(
    token: str = Depends(require_bearer_token),
    settings: Settings = Depends(get_app_settings),
) -> AuthPrincipal:
    return decode_access_token(token=token, settings=settings)


def get_raw_bearer_token(token: str = Depends(require_bearer_token)) -> str:
    return token


def get_auth_session_service(settings: Settings = Depends(get_app_settings)) -> AuthSessionService:
    return AuthSessionService(supabase_url=settings.supabase_url)


async def get_public_transaction_service(
    settings: Settings = Depends(get_app_settings),
    connection: asyncpg.Connection = Depends(get_connection),
) -> AsyncIterator[PublicTransactionService]:
    transaction_repository = TransactionRepository(connection)
    share_link_repository = ShareLinkRepository(connection)
    yield PublicTransactionService(
        transaction_repository=transaction_repository,
        share_link_repository=share_link_repository,
        connection=connection,
        base_url=settings.api_base_url.rstrip("/"),
        share_link_ttl_days=settings.public_share_link_ttl_days,
    )


async def get_consumer_service(
    settings: Settings = Depends(get_app_settings),
    connection: asyncpg.Connection = Depends(get_connection),
) -> AsyncIterator[ConsumerService]:
    user_repository = UserRepository(connection)
    transaction_repository = TransactionRepository(connection)
    share_link_repository = ShareLinkRepository(connection)
    subscription_repository = SubscriptionRepository(connection)
    public_transaction_service = PublicTransactionService(
        transaction_repository=transaction_repository,
        share_link_repository=share_link_repository,
        connection=connection,
        base_url=settings.api_base_url.rstrip("/"),
        share_link_ttl_days=settings.public_share_link_ttl_days,
    )
    yield ConsumerService(
        user_repository=user_repository,
        transaction_repository=transaction_repository,
        subscription_repository=subscription_repository,
        public_transaction_service=public_transaction_service,
    )


async def get_merchant_service(
    settings: Settings = Depends(get_app_settings),
    connection: asyncpg.Connection = Depends(get_connection),
) -> AsyncIterator[MerchantService]:
    user_repository = UserRepository(connection)
    transaction_repository = TransactionRepository(connection)
    share_link_repository = ShareLinkRepository(connection)
    merchant_account_repository = MerchantAccountRepository(connection)
    bank_profile_repository = MerchantBankProfileRepository(connection)
    invite_repository = PendingInviteRepository(connection)
    transaction_service = PublicTransactionService(
        transaction_repository=transaction_repository,
        share_link_repository=share_link_repository,
        connection=connection,
        base_url=settings.api_base_url.rstrip("/"),
        share_link_ttl_days=settings.public_share_link_ttl_days,
    )
    bank_pos_service = BankPosService(
        bank_profile_repository=bank_profile_repository,
        bank_session_repository=BankSessionTokenRepository(connection),
        transaction_repository=transaction_repository,
        client=BancaIntesaPosClient(
            base_url=settings.bank_bib_base_url,
            timeout_seconds=settings.bank_bib_timeout_seconds,
        ),
    )
    yield MerchantService(
        user_repository=user_repository,
        merchant_account_repository=merchant_account_repository,
        bank_profile_repository=bank_profile_repository,
        invite_repository=invite_repository,
        pos_auth_repository=MerchantPosAuthRepository(connection),
        transaction_repository=transaction_repository,
        transaction_service=transaction_service,
        bank_pos_service=bank_pos_service,
        connection=connection,
    )


async def get_pos_service(
    settings: Settings = Depends(get_app_settings),
    connection: asyncpg.Connection = Depends(get_connection),
) -> AsyncIterator[PosService]:
    transaction_repository = TransactionRepository(connection)
    merchant_account_repository = MerchantAccountRepository(connection)
    bank_profile_repository = MerchantBankProfileRepository(connection)
    transaction_service = PublicTransactionService(
        transaction_repository=transaction_repository,
        share_link_repository=ShareLinkRepository(connection),
        connection=connection,
        base_url=settings.api_base_url.rstrip("/"),
        share_link_ttl_days=settings.public_share_link_ttl_days,
    )
    bank_pos_service = BankPosService(
        bank_profile_repository=bank_profile_repository,
        bank_session_repository=BankSessionTokenRepository(connection),
        transaction_repository=transaction_repository,
        client=BancaIntesaPosClient(
            base_url=settings.bank_bib_base_url,
            timeout_seconds=settings.bank_bib_timeout_seconds,
        ),
    )
    yield PosService(
        pos_auth_repository=MerchantPosAuthRepository(connection),
        merchant_account_repository=merchant_account_repository,
        bank_profile_repository=bank_profile_repository,
        transaction_repository=transaction_repository,
        transaction_service=transaction_service,
        bank_pos_service=bank_pos_service,
        session_ttl_hours=settings.pos_session_ttl_hours,
    )


async def get_current_pos_principal(
    token: str = Depends(require_bearer_token),
    service: PosService = Depends(get_pos_service),
) -> PosSessionPrincipal:
    return await service.resolve_session(session_token=token)


async def get_subscription_service(
    settings: Settings = Depends(get_app_settings),
    connection: asyncpg.Connection = Depends(get_connection),
) -> AsyncIterator[SubscriptionService]:
    yield SubscriptionService(
        user_repository=UserRepository(connection),
        merchant_account_repository=MerchantAccountRepository(connection),
        subscription_repository=SubscriptionRepository(connection),
        transaction_repository=TransactionRepository(connection),
        share_link_repository=ShareLinkRepository(connection),
        connection=connection,
        share_link_ttl_days=settings.public_share_link_ttl_days,
    )


async def get_bank_webhook_service(
    settings: Settings = Depends(get_app_settings),
    connection: asyncpg.Connection = Depends(get_connection),
) -> AsyncIterator[BankWebhookService]:
    transaction_repository = TransactionRepository(connection)
    yield BankWebhookService(
        transaction_repository=transaction_repository,
        secret=settings.bank_webhook_secret,
    )
