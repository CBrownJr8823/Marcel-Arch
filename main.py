import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from core.engine import MarcelArchEngine
from core.auditor import MarcelAuditor
from core.invoice import Invoice


# Load environment variables from local .env
load_dotenv()


def normalize_vendor_name(name: str) -> str:
    """Normalize vendor names for comparison."""
    return name.strip().rstrip(".").lower()


async def run_marcel_arch_demo():
    print("🏛️  MARCEL ARCH SYSTEM ONLINE")
    print("-" * 40)

    engine = MarcelArchEngine()
    auditor = MarcelAuditor()

    # 1. Load contract from file
    contract_path = Path("contracts/demo_contract.txt")
    if not contract_path.exists():
        print("❌ Contract file not found: contracts/demo_contract.txt")
        return

    raw_contract = contract_path.read_text(encoding="utf-8")

    # 2. Extract rules from contract
    rules_data = await engine.audit_document(raw_contract)
    print(f"✅ Rules Extracted for Vendor: {rules_data.vendor_name}")

    # 3. Load invoice files from data/
    data_dir = Path("data")
    if not data_dir.exists():
        print("❌ Data folder not found: data/")
        return

    invoice_files = sorted(data_dir.glob("invoice_*.json"))
    if not invoice_files:
        print("❌ No invoice_*.json files found in data/")
        return

    audits_dir = Path("audits")
    audits_dir.mkdir(exist_ok=True)

    # 4. Process each invoice
    for invoice_file in invoice_files:
        print(f"\n📄 Processing invoice file: {invoice_file.name}")

        try:
            invoice_data = json.loads(invoice_file.read_text(encoding="utf-8"))
            invoice = Invoice.model_validate(invoice_data)
        except Exception as e:
            print(f"❌ Failed to load/validate {invoice_file.name}: {e}")
            continue

        # Vendor sanity check
        if normalize_vendor_name(rules_data.vendor_name) != normalize_vendor_name(
            invoice.vendor_name
        ):
            print("⚠️ Vendor name mismatch between contract and invoice.")
            print(f"   Contract: {rules_data.vendor_name}")
            print(f"   Invoice:  {invoice.vendor_name}")

        # Audit invoice
        print("🔍 Auditing Invoice for Leakage...")
        try:
            report = auditor.calculate_leakage(invoice, rules_data.rules)
        except Exception as e:
            print(f"❌ Audit failed for {invoice.invoice_id}: {e}")
            continue

        # Persist audit trail
        audit_path = audits_dir / f"audit_{report.invoice_id}.json"
        with audit_path.open("w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2, default=str)

        print(f"📁 Audit written to: {audit_path}")

        # Verdict & recovery
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
