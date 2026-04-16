import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

import asyncpg

from app.core.errors import Gone, NotFound
from app.domain.models import (
    CreatePosTransactionRequest,
    CreatePublicTransactionRequest,
    MerchantTransactionCreateResponse,
    PublicTransactionCreateResponse,
    PublicTransactionShareResponse,
)
from app.domain.qr import build_nbs_ips_qr_string


class RegularTransactionWriter(Protocol):
    async def create_regular(
        self,
        *,
        payload: CreatePublicTransactionRequest,
        qr_string: str,
        payment_ref: str,
        consumer_user_id: UUID | None,
    ) -> Any: ...

    async def get_public_share_payload(self, *, slug: str) -> Any: ...

    async def create_pos_draft(
        self,
        *,
        merchant_account_id: UUID,
        account_display_name: str,
        payee_name: str,
        payee_address: str | None,
        payee_city: str | None,
        payee_account_number: str,
        payload: CreatePosTransactionRequest,
        qr_string: str,
        payment_ref: str,
    ) -> Any: ...


class ShareLinkWriter(Protocol):
    async def create(
        self, *, transaction_id: UUID, slug: str, qr_string: str, expires_at: datetime
    ) -> Any: ...

    async def increment_access_count(self, *, slug: str) -> None: ...


class PublicTransactionService:
    def __init__(
        self,
        *,
        transaction_repository: RegularTransactionWriter,
        share_link_repository: ShareLinkWriter,
        connection: asyncpg.Connection,
        base_url: str,
        share_link_ttl_days: int,
    ) -> None:
        self.transaction_repository = transaction_repository
        self.share_link_repository = share_link_repository
        self.connection = connection
        self.base_url = base_url
        self.share_link_ttl_days = share_link_ttl_days

    async def create_public_regular(
        self,
        payload: CreatePublicTransactionRequest,
    ) -> PublicTransactionCreateResponse:
        return await self.create_regular_transaction(payload=payload, consumer_user_id=None)

    async def create_consumer_regular(
        self,
        *,
        payload: CreatePublicTransactionRequest,
        consumer_user_id: UUID,
    ) -> PublicTransactionCreateResponse:
        return await self.create_regular_transaction(
            payload=payload, consumer_user_id=consumer_user_id
        )

    async def create_regular_transaction(
        self,
        *,
        payload: CreatePublicTransactionRequest,
        consumer_user_id: UUID | None,
    ) -> PublicTransactionCreateResponse:
        qr_string = build_nbs_ips_qr_string(
            payee_account_number=payload.payee_account_number,
            payee_name=payload.payee_name,
            payee_address=payload.payee_address,
            payee_city=payload.payee_city,
            amount=payload.amount,
            currency=payload.currency,
            payment_code=payload.payment_code,
            payment_description=payload.payment_description,
            payer_name=payload.payer_name,
            payer_address=payload.payer_address,
            payer_city=payload.payer_city,
            reference_model=payload.reference_model,
            reference_number=payload.reference_number,
        )

        payment_ref = self._generate_payment_ref()
        async with self.connection.transaction():
            transaction = await self.transaction_repository.create_regular(
                payload=payload,
                qr_string=qr_string,
                payment_ref=payment_ref,
                consumer_user_id=consumer_user_id,
            )

            slug = self._generate_share_slug()
            expires_at = datetime.now(tz=UTC) + timedelta(days=self.share_link_ttl_days)
            share_link = await self.share_link_repository.create(
                transaction_id=transaction["id"],
                slug=slug,
                qr_string=qr_string,
                expires_at=expires_at,
            )

        return PublicTransactionCreateResponse(
            transaction_id=transaction["id"],
            payment_ref=payment_ref,
            share_slug=share_link["slug"],
            share_url=f"{self.base_url}/v1/public/share/{share_link['slug']}",
            qr_string=qr_string,
            expires_at=share_link["expires_at"],
            status=transaction["status"],
        )

    async def create_pos_draft(
        self,
        *,
        merchant_account_id: UUID,
        account_display_name: str,
        payee_name: str,
        payee_address: str | None,
        payee_city: str | None,
        payee_account_number: str,
        payload: CreatePosTransactionRequest,
    ) -> MerchantTransactionCreateResponse:
        qr_string = build_nbs_ips_qr_string(
            payee_account_number=payee_account_number,
            payee_name=payee_name,
            payee_address=payee_address,
            payee_city=payee_city,
            amount=payload.amount,
            currency="RSD",
            payment_code="289",
            payment_description=payload.payment_description,
            payer_name=None,
            payer_address=None,
            payer_city=None,
            reference_model=payload.reference_model,
            reference_number=payload.reference_number,
        )
        payment_ref = self._generate_payment_ref()
        transaction = await self.transaction_repository.create_pos_draft(
            merchant_account_id=merchant_account_id,
            account_display_name=account_display_name,
            payee_name=payee_name,
            payee_address=payee_address,
            payee_city=payee_city,
            payee_account_number=payee_account_number,
            payload=payload,
            qr_string=qr_string,
            payment_ref=payment_ref,
        )
        return MerchantTransactionCreateResponse(
            transaction_id=transaction["id"],
            payment_ref=payment_ref,
            status=transaction["status"],
            qr_string=qr_string,
        )

    async def get_public_share(self, *, slug: str) -> PublicTransactionShareResponse:
        row = await self.transaction_repository.get_public_share_payload(slug=slug)
        if row is None:
            raise NotFound("Share link does not exist.")
        if row["revoked_at"] is not None or row["expires_at"] <= datetime.now(tz=UTC):
            raise Gone("Share link has expired or was revoked.")

        await self.share_link_repository.increment_access_count(slug=slug)
        return PublicTransactionShareResponse(
            transaction_id=row["transaction_id"],
            payment_ref=row["payment_ref"],
            form_type=row["form_type"],
            status=row["status"],
            payer_name=row["payer_name"],
            payer_address=row["payer_address"],
            payer_city=row["payer_city"],
            payee_name=row["payee_name"],
            payee_address=row["payee_address"],
            payee_city=row["payee_city"],
            payee_account_number=row["payee_account_number"],
            amount=row["amount"],
            currency=row["currency"],
            payment_code=row["payment_code"],
            reference_model=row["reference_model"],
            reference_number=row["reference_number"],
            payment_description=row["payment_description"],
            qr_string=row["qr_string"],
            expires_at=row["expires_at"],
        )

    async def bump_share_access(self, *, slug: str) -> None:
        row = await self.transaction_repository.get_public_share_payload(slug=slug)
        if row is None:
            raise NotFound("Share link does not exist.")
        await self.share_link_repository.increment_access_count(slug=slug)

    @staticmethod
    def _generate_share_slug() -> str:
        return secrets.token_urlsafe(8).rstrip("=").replace("-", "x").replace("_", "y")

    @staticmethod
    def _generate_payment_ref() -> str:
        return f"PLC-{secrets.token_hex(8).upper()}"
