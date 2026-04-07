import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.engine import MarcelArchEngine
from core.engine import AuditResult
from core.auditor import MarcelAuditor, LeakageReport
from core.invoice import Invoice


load_dotenv()

app = FastAPI(
    title="MARCEL ARCH API",
    description="Autonomous Financial Governance & Invoice Leakage Detection",
    version="1.0.0",
)


class AuditRequest(BaseModel):
    contract_text: str = Field(..., min_length=10)
    invoice: Invoice


class AuditResponse(BaseModel):
    extracted_rules: AuditResult
    leakage_report: LeakageReport
    recovery_notice: str


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "marcel-arch"
    }


@app.post("/audit", response_model=AuditResponse)
async def audit_invoice(request: AuditRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        engine = MarcelArchEngine()
        auditor = MarcelAuditor()

        rules_data = await engine.audit_document(request.contract_text)
        report = auditor.calculate_leakage(request.invoice, rules_data.rules)
        recovery_notice = auditor.generate_recovery_notice(report)

        return AuditResponse(
            extracted_rules=rules_data,
            leakage_report=report,
            recovery_notice=recovery_notice,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
