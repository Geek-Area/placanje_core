from decimal import Decimal

from app.domain.qr import build_nbs_ips_qr_string


def test_build_nbs_ips_qr_string_includes_required_fields() -> None:
    qr_string = build_nbs_ips_qr_string(
        payee_account_number="340000000000000001",
        payee_name="Test Primaoc",
        payee_address="Kralja Petra 1",
        payee_city="Beograd",
        amount=Decimal("1200.00"),
        currency="RSD",
        payment_code="289",
        payment_description="Test uplata",
        payer_name="Test Uplatilac",
        payer_address=None,
        payer_city=None,
        reference_model="97",
        reference_number="20260414",
    )

    assert qr_string.startswith("K:PR|V:01|C:1|R:340000000000000001|")
    assert "I:RSD1200,00" in qr_string
    assert "SF:289" in qr_string
    assert "S:Test uplata" in qr_string
    assert "RO:9720260414" in qr_string
