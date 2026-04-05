# --- THE AUDITOR AGENT ---
# We removed result_type from here to fix the 'unknown keyword' error
auditor_agent = Agent(
    'openai:gpt-4o', 
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
        # We tell it the result_type HERE instead of the main Agent call
        print(f"🏛️ MARCEL ARCH [v{self.version}]: Extracting guardrails...")
        result = await auditor_agent.run(secure_text, result_type=AuditResult)
        
        # 3. Security Circuit Breaker
        if self.shield.circuit_breaker(str(result.data)):
            return result.data
        else:
            raise PermissionError("Security Breach detected in AI output.")
