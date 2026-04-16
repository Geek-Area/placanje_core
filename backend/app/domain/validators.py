from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import ValidationFailed
from app.domain.enums import MembershipRole, SubscriptionCadence


def normalize_account_number(value: str) -> str:
    normalized = "".join(character for character in value if character.isdigit())
    if len(normalized) != 18:
        raise ValidationFailed(
            "Payee account number must contain exactly 18 digits.",
            details={"field": "payee_account_number"},
        )
    return normalized


def validate_amount(value: Decimal) -> Decimal:
    if value <= Decimal("0"):
        raise ValidationFailed("Amount must be greater than zero.", details={"field": "amount"})
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_currency(value: str) -> str:
    currency = value.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValidationFailed("Currency must be a 3-letter code.", details={"field": "currency"})
    return currency


def validate_email(value: str, *, field: str) -> str:
    normalized = value.strip().lower()
    if (
        normalized == ""
        or "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
    ):
        raise ValidationFailed(f"{field} must be a valid email address.", details={"field": field})
    return normalized


def validate_payment_code(value: str) -> str:
    payment_code = value.strip()
    if len(payment_code) != 3 or not payment_code.isdigit():
        raise ValidationFailed(
            "Payment code must be a 3-digit string.",
            details={"field": "payment_code"},
        )
    return payment_code


def validate_reference_model(value: str | None) -> str | None:
    if value is None:
        return None
    model = value.strip()
    if model == "":
        return None
    if len(model) != 2 or not model.isdigit():
        raise ValidationFailed(
            "Reference model must be a 2-digit string.",
            details={"field": "reference_model"},
        )
    return model


def validate_reference_number(value: str | None) -> str | None:
    if value is None:
        return None
    reference_number = value.strip()
    if reference_number == "":
        return None
    if len(reference_number) > 35:
        raise ValidationFailed(
            "Reference number must be at most 35 characters.",
            details={"field": "reference_number"},
        )
    return reference_number


def validate_multiline_text(value: str | None, *, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    sanitized = "\n".join(segment.strip() for segment in value.splitlines()).strip()
    if sanitized == "":
        return None
    if len(sanitized) > max_length:
        raise ValidationFailed(
            f"{field} must be at most {max_length} characters.",
            details={"field": field},
        )
    if len(sanitized.splitlines()) > 3:
        raise ValidationFailed(
            f"{field} can contain at most 3 lines.",
            details={"field": field},
        )
    return sanitized


def validate_slug(value: str, *, field: str) -> str:
    slug = value.strip().lower()
    if slug == "":
        raise ValidationFailed(f"{field} must not be empty.", details={"field": field})
    if not all(character.isalnum() or character in {"-", "_"} for character in slug):
        raise ValidationFailed(
            f"{field} can contain only letters, numbers, dashes, and underscores.",
            details={"field": field},
        )
    return slug


def validate_membership_role(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {role.value for role in MembershipRole}:
        raise ValidationFailed(
            "Role must be one of owner, admin, operator, or viewer.",
            details={"field": "role"},
        )
    return normalized


def validate_subscription_cadence(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {cadence.value for cadence in SubscriptionCadence}:
        raise ValidationFailed(
            "Cadence must be one of daily, weekly, or monthly.",
            details={"field": "cadence"},
        )
    return normalized
