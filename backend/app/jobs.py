import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.db import get_pool
from app.repositories.merchant_accounts import MerchantAccountRepository
from app.repositories.share_links import ShareLinkRepository
from app.repositories.subscriptions import SubscriptionRepository
from app.repositories.transactions import TransactionRepository
from app.repositories.users import UserRepository
from app.services.subscriptions import SubscriptionService


async def run_due_subscriptions(limit: int) -> int:
    settings = get_settings()
    pool = await get_pool()
    async with pool.acquire() as connection:
        service = SubscriptionService(
            user_repository=UserRepository(connection),
            merchant_account_repository=MerchantAccountRepository(connection),
            subscription_repository=SubscriptionRepository(connection),
            transaction_repository=TransactionRepository(connection),
            share_link_repository=ShareLinkRepository(connection),
            connection=connection,
            share_link_ttl_days=settings.public_share_link_ttl_days,
        )
        return await service.run_due(limit=limit)


async def expire_pos_transactions(minutes: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as connection:
        repository = TransactionRepository(connection)
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=minutes)
        return await repository.expire_awaiting_payment_transactions(older_than=cutoff)


def main() -> None:
    parser = argparse.ArgumentParser(description="Placanje-Core background jobs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    due_parser = subparsers.add_parser("run-due-subscriptions")
    due_parser.add_argument("--limit", type=int, default=100)

    expire_parser = subparsers.add_parser("expire-pos-transactions")
    expire_parser.add_argument("--minutes", type=int, default=30)

    args = parser.parse_args()

    if args.command == "run-due-subscriptions":
        processed = asyncio.run(run_due_subscriptions(limit=args.limit))
        print(f"processed_subscriptions={processed}")
        return

    result = asyncio.run(expire_pos_transactions(minutes=args.minutes))
    print(result)


if __name__ == "__main__":
    main()
