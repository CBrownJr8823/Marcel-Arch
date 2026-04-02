import os
from typing import List
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from .security import MarcelShield

# --- THE TRUTH SCHEMA ---
class ContractRule(BaseModel):
    """The rigid structure of a Roman Marcel legacy rule."""
    rule_id: str = Field(description="Unique ID, e.g., 'VOLUME_DISCOUNT_01'")
    logic: str = Field(description="The math logic, e.g., 'price * 0.95 if units > 500'")
    value_threshold: float = Field(description="The dollar or unit amount that triggers the rule")

class AuditResult(BaseModel):
    """The final structured output for the CFO."""
    vendor_name: str
    rules: List[ContractRule]

# --- THE AUDITOR AGENT ---
# Ensure you have OPENAI_API_KEY in your .env file
auditor_agent = Agent(
    'openai:gpt-4o', 
    result_type=AuditResult,
    system_prompt=(
        "You are the MARCEL ARCH Autonomous Auditor. "
        "Extract rigid financial rules from contracts. Ignore fluff. "
        "Focus only on pricing, discounts, and penalties."
    )
)

class MarcelArchEngine:
    def __init__(self):
        self.version = "1.0-Roman"
        self.shield = MarcelShield()

    async def audit_document(self, raw_text: str):
        # 1. Security Masking
        secure_text = self.shield.mask_pii(raw_text)
        
        # 2. Agentic Reasoning
        print(f"🏛️ MARCEL ARCH [v{self.version}]: Extracting guardrails...")
        result = await auditor_agent.run(secure_text)
        
        # 3. Security Circuit Breaker
        if self.shield.circuit_breaker(str(result.data)):
            return result.data
        else:
            raise PermissionError("Security Breach detected in AI output.")
