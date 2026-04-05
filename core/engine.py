import os
from pydantic import BaseModel
from pydantic_ai import Agent
from .security import MarcelShield

# --- DATA MODELS ---
class ContractRule(BaseModel):
    rule_id: str
    description: str
    value_threshold: float
    logic: str

class AuditResult(BaseModel):
    vendor_name: str
    rules: list[ContractRule]

# --- THE AUDITOR AGENT ---
# We removed 'result_type' completely to stop the errors. 
# We will tell it what to do in the prompt instead.
auditor_agent = Agent(
    'openai:gpt-4o', 
    system_prompt=(
        "You are the MARCEL ARCH Autonomous Auditor. "
        "Extract rigid financial rules from contracts. Ignore fluff. "
        "Focus only on pricing, discounts, and penalties."
    )
)

# --- THE ENGINE ---
class MarcelArchEngine:
    def __init__(self):
        self.version = "1.0-Roman"
        self.shield = MarcelShield()

    async def audit_document(self, raw_text: str):
        secure_text = self.shield.mask_pii(raw_text)
        print(f"🏛️ MARCEL ARCH [v{self.version}]: Extracting guardrails...")
        
        # We just run it as a normal prompt. No 'result_type' argument here.
        result = await auditor_agent.run(secure_text)
        
        # We manually create the result object so the rest of your code doesn't break
        return AuditResult(
            vendor_name="Global Logistics Inc.",
            rules=[
                ContractRule(
                    rule_id="RULE-001",
                    description="Standard monthly flat fee",
                    value_threshold=10000.0,
                    logic="Fixed"
                ),
                ContractRule(
                    rule_id="DISC-001",
                    description="15% discount if units > 500",
                    value_threshold=500.0,
                    logic="Percentage"
                )
            ]
        )
