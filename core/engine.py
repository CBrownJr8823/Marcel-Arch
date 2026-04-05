import os
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from typing import List
from .security import MarcelShield

# --- DATA MODELS ---
# These define exactly what the AI is looking for
class ContractRule(BaseModel):
    rule_id: str
    description: str
    value_threshold: float
    logic: str

class AuditResult(BaseModel):
    vendor_name: str
    rules: List[ContractRule]

# --- THE AUDITOR AGENT ---
# This is the "Brain" of the operation
auditor_agent = Agent(
    'openai:gpt-4o', 
    result_type=AuditResult, # We define the output type here once
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
        
        # 1. Security Masking (Keeping the data safe)
        secure_text = self.shield.mask_pii(raw_text)
        
        print(f"🏛️ MARCEL ARCH [v{self.version}]: Extracting guardrails...")
        
        # 2. Agentic Reasoning (Calling the Brain)
        # We use simple .run() because result_type is already set in the Agent above
        result = await auditor_agent.run(secure_text)
        
        # 3. Security Circuit Breaker
        # Make sure the AI didn't leak anything before we return the data
        if self.shield.circuit_breaker(str(result.data)):
            return result.data
        else:
            raise PermissionError("Security Breach detected in AI output.")
