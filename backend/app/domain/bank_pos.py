from datetime import UTC, datetime
from decimal import Decimal

from app.domain.qr import _format_party_block, format_nbs_amount


def build_credit_transfer_identificator(*, terminal_identificator: str, sequence: int) -> str:
    now = datetime.now(tz=UTC)
    year = now.strftime("%y")
    julian_day = f"{now.timetuple().tm_yday:03d}"
    transaction_number = f"{sequence % 1_000_000:06d}"
    return f"{terminal_identificator}{year}{julian_day}{transaction_number}"


def build_merchant_pos_scan_qr_string(
    *,
    payee_account_number: str,
    payee_name: str,
    payee_address: str | None,
    payee_city: str | None,
    amount: Decimal,
    currency: str,
    payment_code: str,
    payment_description: str | None,
    mcc: str,
    merchant_reference: str,
    qr_kind: str = "PT",
) -> str:
    fields: list[str] = [
        f"K:{qr_kind}",
        "V:01",
        "C:1",
        f"R:{payee_account_number}",
        f"N:{_format_party_block(payee_name, payee_address, payee_city)}",
        f"I:{format_nbs_amount(currency, amount)}",
        f"SF:{payment_code}",
        f"M:{mcc}",
        f"RP:{merchant_reference}",
    ]

    if payment_description:
        fields.append(f"S:{payment_description}")

    return "|".join(fields)
