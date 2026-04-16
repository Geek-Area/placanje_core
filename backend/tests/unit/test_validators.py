from decimal import Decimal

import pytest

from app.core.errors import ValidationFailed
from app.domain.validators import (
    normalize_account_number,
    validate_amount,
    validate_reference_model,
)


def test_normalize_account_number_removes_spaces_and_dashes() -> None:
    assert normalize_account_number("340-00000000000-0001") == "340000000000000001"


def test_normalize_account_number_rejects_invalid_length() -> None:
    with pytest.raises(ValidationFailed):
        normalize_account_number("12345")


def test_validate_amount_quantizes_to_two_decimals() -> None:
    assert validate_amount(Decimal("1200")) == Decimal("1200.00")


def test_validate_amount_rejects_non_positive_values() -> None:
    with pytest.raises(ValidationFailed):
        validate_amount(Decimal("0"))


def test_reference_model_allows_blank_values() -> None:
    assert validate_reference_model("") is None
