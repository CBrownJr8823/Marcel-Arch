import asyncio
import os
from core.engine import MarcelArchEngine
from core.auditor import MarcelAuditor
from dotenv import load_dotenv

# Load security credentials
load_dotenv()

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

    # 2. THE BRAIN: Extracting Rules
    rules_data = await engine.audit_document(raw_contract)
    print(f"✅ Rules Extracted for Vendor: {rules_data.vendor_name}")

    # 3. THE INVOICE (The Evidence)
    # Scenario: The vendor shipped 620 units (over the 500 limit) but still billed $10,000
    mock_invoice = {
        "invoice_id": "INV-2026-04-03",
        "vendor_name": "Global Logistics Inc",
        "units_purchased": 620,
        "total_amount": 10000.00
    }

    # 4. THE EXECUTIONER: Audit for Leakage
    print("🔍 Auditing Invoice for Leakage...")
    report = auditor.calculate_leakage(mock_invoice, rules_data.rules)

    # 5. THE VERDICT
    print("-" * 40)
    if report.leakage_amount > 0:
        print(f"🚨 LEAKAGE DETECTED: ${report.leakage_amount:,.2f}")
        print(f"📝 REASON: {report.violation_details}")
        print(f"💰 ACTION: Drafted recovery notice for {report.vendor_name}.")
    else:
        print("🟢 AUDIT PASSED: No financial leakage identified.")
    print("-" * 40)

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ ERROR: Please set your OPENAI_API_KEY in the .env file.")
    else:
        asyncio.run(run_marcel_arch_demo())
