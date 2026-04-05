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
# We define the brain here, but we move 'result_type' to the run command
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

    async def audit_document(self, raw_text: str) -> AuditResult:
        """Processes raw contract text into actionable Roman Guardrails."""
        
        # 1. Security Masking
        secure_text = self.shield.mask_pii(raw_text)
        
        print(f"🏛️ MARCEL ARCH [v{self.version}]: Extracting guardrails...")
        
        # 2. Agentic Reasoning 
        # FIX: We put 'result_type' inside the .run() call for your version
        result = await auditor_agent.run(secure_text, result_type=AuditResult)
        
        # 3. Security Circuit Breaker
        if self.shield.circuit_breaker(str(result.data)):
            return result.data
        else:
            raise PermissionError("Security Breach detected in AI output.")
