from decimal import Decimal, ROUND_HALF_UP
from typing import List
from pydantic import BaseModel, Field

from .engine import ContractRule


TWOPLACES = Decimal("0.01")


def to_money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


class LeakageReport(BaseModel):
    invoice_id: str
    vendor_name: str
    expected_amount: Decimal
    actual_billed: Decimal
    leakage_amount: Decimal
    violation_details: str = Field(..., min_length=1)


class MarcelAuditor:
    def calculate_leakage(
        self,
        invoice_ dict,
        contract_rules: List[ContractRule]
    ) -> LeakageReport:
        invoice_id = invoice_data.get("invoice_id", "UNKNOWN")
        vendor_name = invoice_data.get("vendor_name", "UNKNOWN")

        if "total_amount" not in invoice_
            raise ValueError("Invoice is missing total_amount")

        actual_billed = to_money(invoice_data["total_amount"])
        units = int(invoice_data.get("units_purchased", 0))

        expected_amount = actual_billed
        details = "No violations detected."

        for rule in contract_rules:
            logic = getattr(rule, "logic", "") or ""
            threshold = getattr(rule, "value_threshold", None)

            if threshold is None:
                continue

            logic_lower = logic.lower()

            if "discount" in logic_lower and "unit" in logic_lower and units > threshold:
                discount_rate = Decimal("0.15")  # replace with parsed rule value if available
                expected_amount = (actual_billed * (Decimal("1.00") - discount_rate)).quantize(
                    TWOPLACES, rounding=ROUND_HALF_UP
                )
                details = (
                    f"Violation: Missed {int(discount_rate * 100)}% volume discount "
                    f"for exceeding {threshold} units."
                )
                break

        leakage = (actual_billed - expected_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        return LeakageReport(
            invoice_id=invoice_id,
            vendor_name=vendor_name,
            expected_amount=expected_amount,
            actual_billed=actual_billed,
            leakage_amount=leakage,
            violation_details=details
        )
