import re

class MarcelShield:
    """The protective layer for Roman Marcel's legacy."""
    
    @staticmethod
    def mask_pii(text: str) -> str:
        """Removes sensitive data so the AI never sees it."""
        # Mask Emails
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', "[REDACTED_EMAIL]", text)
        # Mask Account/ID Numbers (10-12 digits)
        text = re.sub(r'\b\d{10,12}\b', "[REDACTED_ID]", text)
        # Mask SSN patterns
        text = re.sub(r'\d{3}-\d{2}-\d{4}', "[REDACTED_SSN]", text)
        return text

    @staticmethod
    def circuit_breaker(ai_output: str) -> bool:
        """Stops the AI if it tries to execute dangerous system code."""
        dangerous_terms = ["import os", "rm -rf", "subprocess", "eval(", "exec("]
        if any(term in ai_output.lower() for term in dangerous_terms):
            print("🛑 SECURITY ALERT: AI attempted unauthorized execution.")
            return False
        return True
