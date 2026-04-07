# main.py
import asyncio
import os

from dotenv import load_dotenv

from core.engine import MarcelArchEngine
from core.auditor import MarcelAuditor

load_dotenv()


def normalize_vendor_name(name: str) -> str:
    return name.strip().rstrip(".").lower()


async def run_marcel_arch_demo():
    print("🏛️  MARCEL ARCH SYSTEM ONLINE")
    print("-" * 40)

    engine = MarcelArchEngine()
    auditor = MarcelAuditor()

    raw_contract = """
    Service Agreement: Global Logistics Inc.
    Standard monthly flat fee: $10,000.
    Clause 4.2: If shipping volume exceeds 500 units in a calendar month,
    a 15% discount shall be applied to the total monthly invoice.
    """

    rules_data = await engine.audit_document(raw_contract)
    print(f"✅ Rules Extracted for Vendor: {rules_data.vendor_name}")

    mock_invoice = {
        "invoice_id": "INV-2026-04-05",
        "vendor_name": "Global Logistics Inc",
        "units_purchased": 620,
        "total_amount": 10000.00,
    }

    if normalize_vendor_name(rules_data.vendor_name) != normalize_vendor_name(
        mock_invoice["vendor_name"]
    ):
        print("⚠️ Vendor name mismatch between contract and invoice.")
        print(f"   Contract: {rules_data.vendor_name}")
        print(f"   Invoice:  {mock_invoice['vendor_name']}")

    print("🔍 Auditing Invoice for Leakage...")
    report = auditor.calculate_leakage(mock_invoice, rules_data.rules)

    print("-" * 40)
    if report.leakage_amount > 0:
        print(f"🚨 LEAKAGE DETECTED: ${report.leakage_amount:,.2f}")
        print("\n📝 GENERATING RECOVERY NOTICE:\n")
        print(auditor.generate_recovery_notice(report))
    else:
        print("🟢 AUDIT PASSED: No financial leakage identified.")
    print("-" * 40)


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in local .env")
    else:
        asyncio.run(run_marcel_arch_demo())
