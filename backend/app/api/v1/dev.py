from datetime import UTC, datetime, timedelta

import asyncpg
from fastapi import APIRouter, Depends, status

from app.core.db import get_connection
from app.core.deps import get_subscription_service
from app.domain.models import DevExpirePosTransactionsRequest, DevRunDueSubscriptionsRequest
from app.repositories.transactions import TransactionRepository
from app.services.subscriptions import SubscriptionService

router = APIRouter()


@router.post(
    "/jobs/run-due-subscriptions",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def run_due_subscriptions(
    payload: DevRunDueSubscriptionsRequest,
    service: SubscriptionService = Depends(get_subscription_service),
) -> dict[str, int]:
    processed = await service.run_due(limit=payload.limit)
    return {"processed": processed}


@router.post(
    "/jobs/expire-pos-transactions",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def expire_pos_transactions(
    payload: DevExpirePosTransactionsRequest,
    connection: asyncpg.Connection = Depends(get_connection),
) -> dict[str, str]:
    repository = TransactionRepository(connection)
    result = await repository.expire_awaiting_payment_transactions(
        older_than=datetime.now(tz=UTC) - timedelta(minutes=payload.minutes),
    )
    return {"result": result}
