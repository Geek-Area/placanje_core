from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import get_consumer_service, get_current_principal
from app.domain.auth import AuthPrincipal
from app.domain.models import (
    ConsumerProfileResponse,
    CreatePublicTransactionRequest,
    PublicTransactionCreateResponse,
    SubscriptionListResponse,
    TransactionListResponse,
)
from app.services.consumer import ConsumerService

router = APIRouter()


@router.get("", response_model=ConsumerProfileResponse)
async def get_consumer_profile(
    principal: AuthPrincipal = Depends(get_current_principal),
    service: ConsumerService = Depends(get_consumer_service),
) -> ConsumerProfileResponse:
    return await service.get_profile(principal=principal)


@router.get("/transactions", response_model=TransactionListResponse)
async def list_consumer_transactions(
    principal: AuthPrincipal = Depends(get_current_principal),
    service: ConsumerService = Depends(get_consumer_service),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    return await service.list_transactions(principal=principal, limit=limit, offset=offset)


@router.post(
    "/transactions",
    status_code=status.HTTP_201_CREATED,
    response_model=PublicTransactionCreateResponse,
)
async def create_consumer_transaction(
    payload: CreatePublicTransactionRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: ConsumerService = Depends(get_consumer_service),
) -> PublicTransactionCreateResponse:
    return await service.create_regular_transaction(principal=principal, payload=payload)


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_consumer_subscriptions(
    principal: AuthPrincipal = Depends(get_current_principal),
    service: ConsumerService = Depends(get_consumer_service),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SubscriptionListResponse:
    return await service.list_subscriptions(principal=principal, limit=limit, offset=offset)
