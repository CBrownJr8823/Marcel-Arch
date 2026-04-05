import asyncio
import os
from core.engine import MarcelArchEngine
from core.auditor import MarcelAuditor
from dotenv import load_dotenv

# Load security credentials from your local (now hidden) .env
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

    # 3. THE INVOICE (The Suspect)
    mock_invoice = {
        "invoice_id": "INV-2026-04-05",
        "vendor_name": "Global Logistics Inc",
        "units_purchased": 620,
        "total_amount": 10000.00
    }

    # 4. THE EXECUTIONER: Audit for Leakage
    print("🔍 Auditing Invoice for Leakage...")
    report = auditor.calculate_leakage(mock_invoice, rules_data.rules)

    # 5. THE VERDICT & RECOVERY
    print("-" * 40)
    if report.leakage_amount > 0:
        print(f"🚨 LEAKAGE DETECTED: ${report.leakage_amount:,.2f}")
        
        # Generate the professional recovery notice
        recovery_letter = auditor.generate_recovery_notice(report)
        print("\n📝 GENERATING RECOVERY NOTICE:")
        print(recovery_letter)
        
    else:
        print("🟢 AUDIT PASSED: No financial leakage identified.")
    print("-" * 40)

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ ERROR: OPENAI_API_KEY not found in local .env")
    else:
        asyncio.run(run_marcel_arch_demo())
