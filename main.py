import asyncio
from core.engine import MarcelArchEngine
from core.auditor import MarcelAuditor

async def run_marcel_arch_demo():
    print("🏛️ INITIALIZING MARCEL ARCH SYSTEM...")
    
    engine = MarcelArchEngine()
    auditor = MarcelAuditor()

    # 1. The Raw Contract (Unstructured Data)
    raw_contract = """
    Official Agreement: Global Logistics charges a flat rate of $10,000 for shipping. 
    If monthly volume exceeds 500 units, a 15% discount is applied to the total bill.
    """

    # 2. Extract the "Roman Rules"
    rules_data = await engine.audit_document(raw_contract)
    print(f"✅ Guardrails Extracted for: {rules_data.vendor_name}")

    # 3. The Live Invoice (The 'Suspect' Data)
    # Scenario: They shipped 600 units but still charged $10,000
    mock_invoice = {
        "invoice_id": "INV-2026-001",
        "vendor_name": "Global Logistics",
        "units_purchased": 600,
        "total_amount": 10000.00
    }

    # 4. Run the Audit
    print("🔍 AUDITING LIVE INVOICE...")
    report = auditor.calculate_leakage(mock_invoice, rules_data.rules)

    # 5. The Result
    if report.leakage_amount > 0:
        print(f"🚨 LEAKAGE DETECTED: ${report.leakage_amount:,.2f}")
        print(f"📝 DETAILS: {report.violation_details}")
    else:
        print("🟢 INVOICE COMPLIANT: No leakage found.")

if __name__ == "__main__":
    asyncio.run(run_marcel_arch_demo())
