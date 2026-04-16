from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.domain.validators import (
    normalize_account_number,
    validate_amount,
    validate_currency,
    validate_email,
    validate_membership_role,
    validate_multiline_text,
    validate_payment_code,
    validate_reference_model,
    validate_reference_number,
    validate_slug,
    validate_subscription_cadence,
)


class CreatePublicTransactionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    payer_name: str | None = None
    payer_address: str | None = None
    payer_city: str | None = None
    payee_name: str
    payee_address: str | None = None
    payee_city: str | None = None
    payee_account_number: str
    amount: Decimal
    currency: str = "RSD"
    payment_code: str = "289"
    reference_model: str | None = None
    reference_number: str | None = None
    payment_description: str | None = None

    @field_validator(
        "payer_name", "payer_address", "payer_city", "payment_description", mode="before"
    )
    @classmethod
    def _validate_optional_short_text(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name or "unknown_field"
        return validate_multiline_text(str(value), field=field_name, max_length=70)

    @field_validator("payee_name", "payee_address", "payee_city", mode="before")
    @classmethod
    def _validate_payee_text(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None and info.field_name == "payee_name":
            return None
        if value is None:
            return None
        field_name = info.field_name or "unknown_field"
        return validate_multiline_text(str(value), field=field_name, max_length=70)

    @field_validator("payee_account_number")
    @classmethod
    def _validate_account_number(cls, value: str) -> str:
        return normalize_account_number(value)

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: Decimal) -> Decimal:
        return validate_amount(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency(value)

    @field_validator("payment_code")
    @classmethod
    def _validate_payment_code(cls, value: str) -> str:
        return validate_payment_code(value)

    @field_validator("reference_model")
    @classmethod
    def _validate_reference_model(cls, value: str | None) -> str | None:
        return validate_reference_model(value)

    @field_validator("reference_number")
    @classmethod
    def _validate_reference_number(cls, value: str | None) -> str | None:
        return validate_reference_number(value)


class PublicTransactionCreateResponse(BaseModel):
    transaction_id: UUID
    payment_ref: str
    share_slug: str
    share_url: str
    qr_string: str
    expires_at: datetime
    status: str


class PublicTransactionShareResponse(BaseModel):
    transaction_id: UUID
    payment_ref: str
    form_type: str
    status: str
    payer_name: str | None
    payer_address: str | None
    payer_city: str | None
    payee_name: str
    payee_address: str | None
    payee_city: str | None
    payee_account_number: str
    amount: Decimal
    currency: str
    payment_code: str
    reference_model: str | None
    reference_number: str | None
    payment_description: str | None
    qr_string: str
    expires_at: datetime


class ConsumerProfileResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str | None
    consumer_registered: bool
    merchant_registered: bool


class TransactionSummaryResponse(BaseModel):
    id: UUID
    form_type: str
    status: str
    payment_ref: str
    amount: Decimal
    currency: str
    payment_code: str
    payment_description: str | None
    payee_name: str
    payee_account_number: str
    merchant_account_id: UUID | None
    reference_model: str | None
    reference_number: str | None
    bank_transaction_ref: str | None
    completed_at: datetime | None
    created_at: datetime


class SubscriptionSummaryResponse(BaseModel):
    id: UUID
    merchant_account_id: UUID
    subscriber_email: str
    subscriber_name: str | None
    cadence: str
    next_run_at: datetime
    last_run_at: datetime | None
    active: bool
    template: dict[str, object]
    created_at: datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionSummaryResponse]
    limit: int
    offset: int


class SubscriptionListResponse(BaseModel):
    items: list[SubscriptionSummaryResponse]
    limit: int
    offset: int


class MerchantSignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str
    slug: str | None = None
    legal_entity_name: str | None = None
    legal_entity_id: str | None = None
    payee_name: str | None = None
    payee_account_number: str
    payee_address: str | None = None
    payee_city: str | None = None
    subscription_tier: str | None = None

    @field_validator(
        "display_name",
        "legal_entity_name",
        "legal_entity_id",
        "payee_name",
        "payee_address",
        "payee_city",
        "subscription_tier",
        mode="before",
    )
    @classmethod
    def _validate_text_fields(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name or "unknown_field"
        max_length = 120 if info.field_name in {"display_name", "legal_entity_name"} else 70
        return validate_multiline_text(str(value), field=field_name, max_length=max_length)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_slug(value, field="slug")

    @field_validator("payee_account_number")
    @classmethod
    def _validate_account_number(cls, value: str) -> str:
        return normalize_account_number(value)


class MerchantAccountCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str
    slug: str | None = None
    payee_name: str | None = None
    payee_account_number: str | None = None
    payee_address: str | None = None
    payee_city: str | None = None

    @field_validator("display_name", "payee_name", "payee_address", "payee_city", mode="before")
    @classmethod
    def _validate_text_fields(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name or "unknown_field"
        return validate_multiline_text(str(value), field=field_name, max_length=70)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_slug(value, field="slug")

    @field_validator("payee_account_number")
    @classmethod
    def _validate_account_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_account_number(value)


class MerchantAccountResponse(BaseModel):
    id: UUID
    parent_account_id: UUID | None
    account_type: str
    slug: str
    display_name: str
    payee_name: str
    payee_account_number: str | None
    payee_address: str | None
    payee_city: str | None
    active: bool
    effective_role: str | None


class MerchantAccountListResponse(BaseModel):
    items: list[MerchantAccountResponse]


class MerchantInviteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str
    role: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return validate_email(value, field="email")

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        return validate_membership_role(value)


class MerchantInviteResponse(BaseModel):
    status: str
    invitation_mode: str
    account_id: UUID
    invited_email: str
    role: str
    token: str | None = None


class AcceptInviteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    token: str

    @field_validator("token")
    @classmethod
    def _validate_token(cls, value: str) -> str:
        token = value.strip()
        if token == "":
            raise ValueError("token must not be empty")
        return token


class AcceptInviteResponse(BaseModel):
    status: str
    account_id: UUID
    role: str


class CreatePosTransactionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    amount: Decimal
    payment_description: str | None = None
    reference_model: str | None = None
    reference_number: str | None = None

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: Decimal) -> Decimal:
        return validate_amount(value)

    @field_validator("payment_description", mode="before")
    @classmethod
    def _validate_description(cls, value: object) -> str | None:
        if value is None:
            return None
        return validate_multiline_text(str(value), field="payment_description", max_length=70)

    @field_validator("reference_model")
    @classmethod
    def _validate_reference_model(cls, value: str | None) -> str | None:
        return validate_reference_model(value)

    @field_validator("reference_number")
    @classmethod
    def _validate_reference_number(cls, value: str | None) -> str | None:
        return validate_reference_number(value)


class MerchantTransactionCreateResponse(BaseModel):
    transaction_id: UUID
    payment_ref: str
    status: str
    qr_string: str


class MerchantAccountStatsResponse(BaseModel):
    account_id: UUID
    total_transactions: int
    completed_transactions: int
    awaiting_payment_transactions: int
    expired_transactions: int
    total_completed_amount: Decimal


class CreateSubscriptionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subscriber_email: str
    subscriber_name: str | None = None
    amount: Decimal
    currency: str = "RSD"
    payment_code: str = "289"
    reference_model: str | None = None
    reference_number: str | None = None
    payment_description: str | None = None
    cadence: str
    first_run_at: datetime

    @field_validator("subscriber_email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return validate_email(value, field="subscriber_email")

    @field_validator("subscriber_name", "payment_description", mode="before")
    @classmethod
    def _validate_optional_text(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name or "unknown_field"
        return validate_multiline_text(str(value), field=field_name, max_length=70)

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: Decimal) -> Decimal:
        return validate_amount(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency(value)

    @field_validator("payment_code")
    @classmethod
    def _validate_payment_code(cls, value: str) -> str:
        return validate_payment_code(value)

    @field_validator("reference_model")
    @classmethod
    def _validate_reference_model(cls, value: str | None) -> str | None:
        return validate_reference_model(value)

    @field_validator("reference_number")
    @classmethod
    def _validate_reference_number(cls, value: str | None) -> str | None:
        return validate_reference_number(value)

    @field_validator("cadence")
    @classmethod
    def _validate_cadence(cls, value: str) -> str:
        return validate_subscription_cadence(value)


class SubscriptionMutationResponse(BaseModel):
    id: UUID
    active: bool
    next_run_at: datetime


class DevRunDueSubscriptionsRequest(BaseModel):
    limit: int = 100


class DevExpirePosTransactionsRequest(BaseModel):
    minutes: int = 30


class BankWebhookStatusPayload(BaseModel):
    payment_ref: str
    bank_transaction_ref: str
    status: str
    amount: Decimal
    completed_at: datetime
