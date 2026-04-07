from decimal import Decimal, ROUND_HALF_UP
from typing import List

from pydantic import BaseModel, Field

from .engine import ContractRule
from .invoice import Invoice


TWOPLACES = Decimal("0.01")


def to_money(value) -> Decimal:
    """Convert a number or string into a Decimal with 2 decimal places."""
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


class LeakageReport(BaseModel):
    """Structured audit result for one invoice."""
    invoice_id: str
    vendor_name: str
    expected_amount: Decimal
    actual_billed: Decimal
    leakage_amount: Decimal
    violation_details: str = Field(..., min_length=1)


class MarcelAuditor:
    """Executes contract rules against validated invoices."""

    def calculate_leakage(
        self,
        invoice: Invoice,
        contract_rules: List[ContractRule],
    ) -> LeakageReport:
        """
        Compare one invoice against extracted contract rules and compute leakage.
        Current v1 focus: volume-based discount detection.
        """
        invoice_id = invoice.invoice_id
        vendor_name = invoice.vendor_name

        actual_billed = to_money(invoice.total_amount)
        units = int(invoice.units_purchased or 0)

        expected_amount = actual_billed
        details = "No violations detected."

        for rule in contract_rules:
            logic = (rule.logic or "").lower()
            threshold = rule.value_threshold
            discount_percent = rule.discount_percent

            if threshold is None:
                continue

            # v1 rule type: volume discount
            if "unit" in logic and "discount" in logic and units > threshold:
                rate = (
                    discount_percent / Decimal("100")
                    if discount_percent is not None
                    else Decimal("0.15")
                )

                expected_amount = (
                    actual_billed * (Decimal("1.00") - rate)
                ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

                details = (
                    f"Violation: Missed {int(rate * 100)}% volume discount "
                    f"for exceeding {threshold} units."
                )
                break

        leakage = (actual_billed - expected_amount).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )

        return LeakageReport(
            invoice_id=invoice_id,
            vendor_name=vendor_name,
            expected_amount=expected_amount,
            actual_billed=actual_billed,
            leakage_amount=leakage,
            violation_details=details,
        )

    def generate_recovery_notice(self, report: LeakageReport) -> str:
        """Generate a professional recovery notice for AP/AR follow-up."""
        if report.leakage_amount <= 0:
            return "No recovery action required."

        return (
            f"Subject: Billing Discrepancy on Invoice {report.invoice_id}\n\n"
            f"Dear Accounts Receivable,\n\n"
            f"Our internal audit of invoice {report.invoice_id} from "
            f"{report.vendor_name} identified a billing discrepancy.\n\n"
            f"{report.violation_details}\n\n"
            f"Based on the contractual terms, the expected amount is "
            f"${report.expected_amount:,.2f}, while the invoice was billed at "
            f"${report.actual_billed:,.2f}.\n\n"
            f"This results in an overcharge of "
            f"${report.leakage_amount:,.2f}. Please confirm issuance of a "
            f"credit memo or revised invoice reflecting the correct amount.\n\n"
            f"Sincerely,\n"
            f"MARCEL ARCH Autonomous Auditor"
        )
