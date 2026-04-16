from decimal import Decimal


def _format_party_block(name: str, address: str | None, city: str | None) -> str:
    lines = [name.strip()]
    if address:
        lines.append(address.strip())
    if city:
        lines.append(city.strip())
    return "\n".join(line for line in lines if line)


def format_nbs_amount(currency: str, amount: Decimal) -> str:
    return f"{currency}{amount:.2f}".replace(".", ",")


def build_nbs_ips_qr_string(
    *,
    payee_account_number: str,
    payee_name: str,
    payee_address: str | None,
    payee_city: str | None,
    amount: Decimal,
    currency: str,
    payment_code: str,
    payment_description: str | None,
    payer_name: str | None,
    payer_address: str | None,
    payer_city: str | None,
    reference_model: str | None,
    reference_number: str | None,
) -> str:
    fields: list[str] = [
        "K:PR",
        "V:01",
        "C:1",
        f"R:{payee_account_number}",
        f"N:{_format_party_block(payee_name, payee_address, payee_city)}",
        f"I:{format_nbs_amount(currency, amount)}",
        f"SF:{payment_code}",
    ]

    if payer_name:
        fields.append(f"P:{_format_party_block(payer_name, payer_address, payer_city)}")
    if payment_description:
        fields.append(f"S:{payment_description}")
    if reference_number:
        model = reference_model or "00"
        fields.append(f"RO:{model}{reference_number}")

    return "|".join(fields)
