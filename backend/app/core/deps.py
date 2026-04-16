from collections.abc import AsyncIterator

import asyncpg
from fastapi import Depends

from app.core.auth import decode_access_token, require_bearer_token
from app.core.config import Settings, get_settings
from app.core.db import get_connection
from app.domain.auth import AuthPrincipal
from app.repositories.invites import PendingInviteRepository
from app.repositories.merchant_accounts import MerchantAccountRepository
from app.repositories.share_links import ShareLinkRepository
from app.repositories.subscriptions import SubscriptionRepository
from app.repositories.transactions import TransactionRepository
from app.repositories.users import UserRepository
from app.services.bank_webhooks import BankWebhookService
from app.services.consumer import ConsumerService
from app.services.merchant import MerchantService
from app.services.subscriptions import SubscriptionService
from app.services.transactions import PublicTransactionService


def get_app_settings() -> Settings:
    return get_settings()


def get_current_principal(
    token: str = Depends(require_bearer_token),
    settings: Settings = Depends(get_app_settings),
) -> AuthPrincipal:
    return decode_access_token(token=token, settings=settings)


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
    invite_repository = PendingInviteRepository(connection)
    transaction_service = PublicTransactionService(
        transaction_repository=transaction_repository,
        share_link_repository=share_link_repository,
        connection=connection,
        base_url=settings.api_base_url.rstrip("/"),
        share_link_ttl_days=settings.public_share_link_ttl_days,
    )
    yield MerchantService(
        user_repository=user_repository,
        merchant_account_repository=merchant_account_repository,
        invite_repository=invite_repository,
        transaction_repository=transaction_repository,
        transaction_service=transaction_service,
        connection=connection,
    )


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
