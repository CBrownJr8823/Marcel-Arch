import asyncio
import os

from dotenv import load_dotenv

from core.engine import MarcelArchEngine
from core.auditor import MarcelAuditor


# Load environment variables from .env (OPENAI_API_KEY, etc.)
load_dotenv()


def normalize_vendor_name(name: str) -> str:
    """Normalize vendor names for comparison."""
    return name.strip().rstrip(".").lower()


async def run_marcel_arch_demo():
    print("🏛️  MARCEL ARCH SYSTEM ONLINE")
    print("-" * 40)

    engine = MarcelArchEngine()
    auditor = MarcelAuditor()

    # 1. THE CONTRACT (The Law)
    raw_contract = """
    Service Agreement: Global Logistics Inc.
    Standard monthly flat fee: $10,000.
    Clause 4.2: If shipping volume exceeds 500 units in a calendar month,
    a 15% discount shall be applied to the total monthly invoice.
    """

    # 2. Extract rules from the contract
    rules_data = await engine.audit_document(raw_contract)
    print(f"✅ Rules Extracted for Vendor: {rules_data.vendor_name}")

    # 3. THE INVOICE (The Suspect)
    mock_invoice = {
        "invoice_id": "INV-2026-04-05",
        "vendor_name": "Global Logistics Inc",
        "units_purchased": 620,
        "total_amount": 10000.00,
    }

    # 4. Vendor sanity check
    if normalize_vendor_name(rules_data.vendor_name) != normalize_vendor_name(
        mock_invoice["vendor_name"]
    ):
        print("⚠️ Vendor name mismatch between contract and invoice.")
        print(f"   Contract: {rules_data.vendor_name}")
        print(f"   Invoice:  {mock_invoice['vendor_name']}")

    # 5. THE EXECUTIONER: Audit for Leakage
    print("🔍 Auditing Invoice for Leakage...")
    report = auditor.calculate_leakage(mock_invoice, rules_data.rules)

    # 6. THE VERDICT & RECOVERY
    print("-" * 40)
    if report.leakage_amount > 0:
        print(f"🚨 LEAKAGE DETECTED: ${report.leakage_amount:,.2f}")
        print("\n📝 GENERATING RECOVERY NOTICE:\n")
        recovery_letter = auditor.generate_recovery_notice(report)
        print(recovery_letter)
    else:
        print("🟢 AUDIT PASSED: No financial leakage identified.")
    print("-" * 40)


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in local .env")
        print("   Create a .env file in the project root with:")
        print("   OPENAI_API_KEY=sk-your-real-key-here")
    else:
        asyncio.run(run_marcel_arch_demo())
