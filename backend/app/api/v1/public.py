from fastapi import APIRouter, Depends, status

from app.core.deps import get_public_transaction_service
from app.domain.models import (
    CreatePublicTransactionRequest,
    PublicTransactionCreateResponse,
    PublicTransactionShareResponse,
)
from app.services.transactions import PublicTransactionService

router = APIRouter()


@router.post(
    "/transactions",
    status_code=status.HTTP_201_CREATED,
    response_model=PublicTransactionCreateResponse,
)
async def create_public_transaction(
    payload: CreatePublicTransactionRequest,
    service: PublicTransactionService = Depends(get_public_transaction_service),
) -> PublicTransactionCreateResponse:
    return await service.create_public_regular(payload)


@router.get("/share/{slug}", response_model=PublicTransactionShareResponse)
async def get_public_share(
    slug: str,
    service: PublicTransactionService = Depends(get_public_transaction_service),
) -> PublicTransactionShareResponse:
    return await service.get_public_share(slug=slug)


@router.post("/share/{slug}/access", status_code=status.HTTP_202_ACCEPTED)
async def bump_public_share_access(
    slug: str,
    service: PublicTransactionService = Depends(get_public_transaction_service),
) -> dict[str, str]:
    await service.bump_share_access(slug=slug)
    return {"status": "accepted"}
