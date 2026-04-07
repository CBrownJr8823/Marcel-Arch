from decimal import Decimal
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from .security import MarcelShield


class ContractRule(BaseModel):
    rule_id: str
    description: str
    value_threshold: Decimal | int | None = None
    discount_percent: Decimal | None = None
    logic: str


class AuditResult(BaseModel):
    vendor_name: str = Field(..., min_length=1)
    rules: list[ContractRule]


auditor_agent = Agent(
    "openai:gpt-4o",
    output_type=AuditResult,
    system_prompt=(
        "You are the MARCEL ARCH Autonomous Auditor. "
        "Extract only explicit financial rules from contracts. "
        "Return the vendor name and a list of rules. "
        "Include only pricing, discounts, penalties, thresholds, and billing logic. "
        "Do not invent terms that are not present in the contract."
    ),
)


class MarcelArchEngine:
    def __init__(self):
        self.version = "1.0-Roman"
        self.shield = MarcelShield()

    async def audit_document(self, raw_text: str) -> AuditResult:
        secure_text = self.shield.mask_pii(raw_text)
        print(f"🏛️ MARCEL ARCH [v{self.version}]: Extracting guardrails...")

        result = await auditor_agent.run(secure_text)
        return result.output
