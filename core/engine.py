from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .security import MarcelShield


class ContractRule(BaseModel):
    """A single financial rule extracted from a contract."""
    rule_id: str
    description: str
    value_threshold: Decimal | int | None = None
    discount_percent: Decimal | None = None
    logic: str = Field(
        ...,
        description=(
            "Plain-English description of how to apply this rule "
            "(e.g. 'if units > 500 then apply 15% discount')."
        ),
    )


class AuditResult(BaseModel):
    """Structured representation of a contract: vendor + rules."""
    vendor_name: str = Field(..., min_length=1)
    rules: List[ContractRule]


# Pydantic‑AI agent that returns structured AuditResult
auditor_agent = Agent(
    "openai:gpt-4o",
    output_type=AuditResult,
    system_prompt=(
        "You are the MARCEL ARCH Autonomous Auditor.\n"
        "Task: Extract only explicit financial rules from contracts.\n"
        "Return:\n"
        "- vendor_name: exact legal vendor name as written.\n"
        "- rules: list of ContractRule objects.\n"
        "For each rule, capture thresholds (units, amounts) and any "
        "discount_percent if stated.\n"
        "Include pricing, discounts, penalties, and billing logic only.\n"
        "Do NOT invent terms not present in the text."
    ),
)


class MarcelArchEngine:
    """Engine that turns raw contract text into executable guardrails."""

    def __init__(self) -> None:
        self.version = "1.0-Roman"
        self.shield = MarcelShield()

    async def audit_document(self, raw_text: str) -> AuditResult:
        """
        Ingest a raw contract string and return an AuditResult
        with vendor_name and extracted ContractRule items.
        """
        secure_text = self.shield.mask_pii(raw_text)
        print(f"🏛️ MARCEL ARCH [v{self.version}]: Extracting guardrails...")

        result = await auditor_agent.run(secure_text)
        return result.output
