from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import get_current_pos_principal, get_pos_service, get_raw_bearer_token
from app.domain.auth import PosSessionPrincipal
from app.domain.models import (
    CreatePosTransactionRequest,
    LogoutResponse,
    MerchantAccountStatsResponse,
    MerchantTransactionCreateResponse,
    PosLoginRequest,
    PosLoginResponse,
    PosSessionResponse,
    TransactionListResponse,
    TransactionSummaryResponse,
)
from app.services.pos import PosService

router = APIRouter()


@router.post("/session", status_code=status.HTTP_201_CREATED, response_model=PosLoginResponse)
async def login_pos(
    payload: PosLoginRequest,
    service: PosService = Depends(get_pos_service),
) -> PosLoginResponse:
    return await service.login(payload=payload)


@router.get("/session", response_model=PosSessionResponse)
async def get_pos_session(
    principal: PosSessionPrincipal = Depends(get_current_pos_principal),
    service: PosService = Depends(get_pos_service),
) -> PosSessionResponse:
    return await service.get_session(principal=principal)


@router.post("/logout", response_model=LogoutResponse)
async def logout_pos(
    access_token: str = Depends(get_raw_bearer_token),
    service: PosService = Depends(get_pos_service),
) -> LogoutResponse:
    return await service.logout(session_token=access_token)


@router.post(
    "/transactions",
    status_code=status.HTTP_201_CREATED,
    response_model=MerchantTransactionCreateResponse,
)
async def create_pos_transaction(
    payload: CreatePosTransactionRequest,
    principal: PosSessionPrincipal = Depends(get_current_pos_principal),
    service: PosService = Depends(get_pos_service),
) -> MerchantTransactionCreateResponse:
    return await service.create_pos_transaction(principal=principal, payload=payload)


@router.get("/transactions", response_model=TransactionListResponse)
async def list_pos_transactions(
    principal: PosSessionPrincipal = Depends(get_current_pos_principal),
    service: PosService = Depends(get_pos_service),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    return await service.list_transactions(principal=principal, limit=limit, offset=offset)


@router.get("/stats", response_model=MerchantAccountStatsResponse)
async def get_pos_stats(
    principal: PosSessionPrincipal = Depends(get_current_pos_principal),
    service: PosService = Depends(get_pos_service),
) -> MerchantAccountStatsResponse:
    return await service.get_stats(principal=principal)


@router.post(
    "/transactions/{transaction_id}/sync-bank-status",
    response_model=TransactionSummaryResponse,
)
async def sync_pos_bank_status(
    transaction_id: UUID,
    principal: PosSessionPrincipal = Depends(get_current_pos_principal),
    service: PosService = Depends(get_pos_service),
) -> TransactionSummaryResponse:
    return await service.sync_bank_transaction_status(
        principal=principal, transaction_id=transaction_id
    )
