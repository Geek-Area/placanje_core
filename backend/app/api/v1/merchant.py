from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import get_current_principal, get_merchant_service, get_subscription_service
from app.domain.auth import AuthPrincipal
from app.domain.models import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    CreatePosTransactionRequest,
    CreateSubscriptionRequest,
    MerchantAccountCreateRequest,
    MerchantAccountListResponse,
    MerchantAccountResponse,
    MerchantAccountStatsResponse,
    MerchantInviteRequest,
    MerchantInviteResponse,
    MerchantSignupRequest,
    MerchantTransactionCreateResponse,
    SubscriptionMutationResponse,
    SubscriptionSummaryResponse,
    TransactionListResponse,
)
from app.services.merchant import MerchantService
from app.services.subscriptions import SubscriptionService

router = APIRouter()


@router.get("/accounts", response_model=MerchantAccountListResponse)
async def list_merchant_accounts(
    principal: AuthPrincipal = Depends(get_current_principal),
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantAccountListResponse:
    return await service.list_accounts(principal=principal)


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=MerchantAccountResponse)
async def signup_merchant(
    payload: MerchantSignupRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantAccountResponse:
    return await service.signup_owner(principal=principal, payload=payload)


@router.post(
    "/accounts/{account_id}/sub-accounts",
    status_code=status.HTTP_201_CREATED,
    response_model=MerchantAccountResponse,
)
async def create_sub_account(
    account_id: UUID,
    payload: MerchantAccountCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantAccountResponse:
    return await service.create_sub_account(
        principal=principal,
        parent_account_id=account_id,
        payload=payload,
    )


@router.post(
    "/accounts/{account_id}/invites",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MerchantInviteResponse,
)
async def invite_cashier(
    account_id: UUID,
    payload: MerchantInviteRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantInviteResponse:
    return await service.invite_cashier(principal=principal, account_id=account_id, payload=payload)


@router.post("/invites/accept", response_model=AcceptInviteResponse)
async def accept_invite(
    payload: AcceptInviteRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: MerchantService = Depends(get_merchant_service),
) -> AcceptInviteResponse:
    return await service.accept_invite(principal=principal, token=payload.token)


@router.post(
    "/accounts/{account_id}/transactions",
    status_code=status.HTTP_201_CREATED,
    response_model=MerchantTransactionCreateResponse,
)
async def create_pos_transaction(
    account_id: UUID,
    payload: CreatePosTransactionRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantTransactionCreateResponse:
    return await service.create_pos_transaction(
        principal=principal, account_id=account_id, payload=payload
    )


@router.get("/accounts/{account_id}/transactions", response_model=TransactionListResponse)
async def list_account_transactions(
    account_id: UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: MerchantService = Depends(get_merchant_service),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    return await service.list_account_transactions(
        principal=principal,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )


@router.get("/accounts/{account_id}/stats", response_model=MerchantAccountStatsResponse)
async def get_account_stats(
    account_id: UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantAccountStatsResponse:
    return await service.get_account_stats(principal=principal, account_id=account_id)


@router.post(
    "/accounts/{account_id}/subscriptions",
    status_code=status.HTTP_201_CREATED,
    response_model=SubscriptionSummaryResponse,
    include_in_schema=False,
)
async def create_subscription(
    account_id: UUID,
    payload: CreateSubscriptionRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionSummaryResponse:
    return await service.create(principal=principal, account_id=account_id, payload=payload)


@router.post(
    "/subscriptions/{subscription_id}/pause",
    response_model=SubscriptionMutationResponse,
    include_in_schema=False,
)
async def pause_subscription(
    subscription_id: UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionMutationResponse:
    return await service.pause(principal=principal, subscription_id=subscription_id)


@router.post(
    "/subscriptions/{subscription_id}/resume",
    response_model=SubscriptionMutationResponse,
    include_in_schema=False,
)
async def resume_subscription(
    subscription_id: UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionMutationResponse:
    return await service.resume(principal=principal, subscription_id=subscription_id)
