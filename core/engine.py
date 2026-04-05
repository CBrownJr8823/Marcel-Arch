import os
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from typing import List
from .security import MarcelShield

# --- DATA MODELS ---
class ContractRule(BaseModel):
    rule_id: str
    description: str
    value_threshold: float
    logic: str

class AuditResult(BaseModel):
    vendor_name: str
    rules: List[ContractRule]

# --- THE AUDITOR AGENT ---
# FIX: In your version, 'result_type' MUST be here, at the start.
auditor_agent = Agent(
    'openai:gpt-4o', 
    result_type=AuditResult, 
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

    async def audit_document(self, raw_text: str) -> AuditResult:
        """Processes raw contract text into actionable Roman Guardrails."""
        secure_text = self.shield.mask_pii(raw_text)
        print(f"🏛️ MARCEL ARCH [v{self.version}]: Extracting guardrails...")
        
        # FIX: In your version, the .run() command must be empty of arguments 
        # except for the text itself.
        result = await auditor_agent.run(secure_text)
        
        return result.data
