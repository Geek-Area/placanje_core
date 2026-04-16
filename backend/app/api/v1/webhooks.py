from fastapi import APIRouter, Depends, Header, status

from app.core.deps import get_bank_webhook_service
from app.domain.models import BankWebhookStatusPayload
from app.services.bank_webhooks import BankWebhookService

router = APIRouter()


@router.post("/bank/{provider}/ips-status", status_code=status.HTTP_200_OK)
async def receive_bank_status(
    provider: str,
    payload: BankWebhookStatusPayload,
    x_signature: str = Header(alias="X-Signature"),
    service: BankWebhookService = Depends(get_bank_webhook_service),
) -> dict[str, str]:
    await service.process_status_update(provider=provider, payload=payload, signature=x_signature)
    return {"status": "ok"}
