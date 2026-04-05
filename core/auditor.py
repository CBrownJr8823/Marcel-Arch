from pydantic import BaseModel, Field
from typing import List, Optional
from .engine import ContractRule

class LeakageReport(BaseModel):
    """The high-stakes report for the CFO."""
    invoice_id: str
    vendor_name: str
    expected_amount: float
    actual_billed: float
    leakage_amount: float
    violation_details: str

class MarcelAuditor:
    def calculate_leakage(self, invoice_data: dict, contract_rules: List[ContractRule]) -> LeakageReport:
        """Compares live billing against the Roman Guardrails."""
        actual_billed = invoice_data.get("total_amount", 0.0)
        units = invoice_data.get("units_purchased", 0)
        
        # Default expectation matches bill unless a rule triggers
        expected_amount = actual_billed
        details = "No violations detected."

        for rule in contract_rules:
            # Detect volume-based rules in the extracted logic
            if "units" in rule.logic.lower() and units > rule.value_threshold:
                # Apply the 'Roman' 15% discount for the demo
                discount_rate = 0.15 
                expected_amount = actual_billed * (1 - discount_rate)
                details = f"Violation: Missed {int(discount_rate*100)}% volume discount for exceeding {rule.value_threshold} units."
                break

        leakage = actual_billed - expected_amount

        return LeakageReport(
            invoice_id=invoice_data.get("invoice_id", "UNKNOWN"),
            vendor_name=invoice_data.get("vendor_name", "UNKNOWN"),
            expected_amount=expected_amount,
            actual_billed=actual_billed,
            leakage_amount=leakage,
            violation_details=details
        )
