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

    raw_contract = """
    Service Agreement: Global Logistics Inc.
    Standard monthly flat fee: $10,000.
    Clause 4.2: If shipping volume exceeds 500 units in a calendar month,
    a 15% discount shall be applied to the total monthly invoice.
    """

    mock_invoice = {
        "invoice_id": "INV-2026-04-05",
        "vendor_name": "Global Logistics Inc",
        "units_purchased": 620,
        "total_amount": 10000.00
    }

    try:
        engine = MarcelArchEngine()
        auditor = MarcelAuditor()
    except Exception as e:
        print(f"❌ Failed to initialize system components: {e}")
        return

    try:
        rules_data = await engine.audit_document(raw_contract)
    except Exception as e:
        print(f"❌ Failed to extract rules from contract: {e}")
        return

    if not rules_
        print("❌ No rules data returned from engine.")
        return

    vendor_name = getattr(rules_data, "vendor_name", None)
    rules = getattr(rules_data, "rules", None)

    if not vendor_name or not rules:
        print("❌ rules_data is missing vendor_name or rules.")
        return

    print(f"✅ Rules Extracted for Vendor: {vendor_name}")

    if normalize_vendor_name(vendor_name) != normalize_vendor_name(mock_invoice["vendor_name"]):
        print("⚠️ Vendor name mismatch between contract and invoice.")
        print(f"   Contract: {vendor_name}")
        print(f"   Invoice:  {mock_invoice['vendor_name']}")

    print("🔍 Auditing Invoice for Leakage...")

    try:
        report = auditor.calculate_leakage(mock_invoice, rules)
    except Exception as e:
        print(f"❌ Failed during leakage calculation: {e}")
        return

    leakage_amount = getattr(report, "leakage_amount", None)
    if leakage_amount is None:
        print("❌ Report is missing leakage_amount.")
        return

    print("-" * 40)
    if leakage_amount > 0:
        print(f"🚨 LEAKAGE DETECTED: ${leakage_amount:,.2f}")

        try:
            recovery_letter = auditor.generate_recovery_notice(report)
            print("\n📝 GENERATING RECOVERY NOTICE:")
            print(recovery_letter)
        except Exception as e:
            print(f"❌ Failed to generate recovery notice: {e}")
    else:
        print("🟢 AUDIT PASSED: No financial leakage identified.")

    print("-" * 40)


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in local .env")
    else:
        asyncio.run(run_marcel_arch_demo())
