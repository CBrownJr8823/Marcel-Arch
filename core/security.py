import re


class MarcelShield:
    """Basic prompt-sanitization and output-screening utilities."""

    # Precompiled regex patterns
    EMAIL_RE = re.compile(
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    )
    ID_RE = re.compile(r"\b\d{10,12}\b")
    SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    DANGEROUS_PATTERNS = [
        re.compile(r"\bimport\s+os\b", re.IGNORECASE),
        re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
        re.compile(r"\bsubprocess\b", re.IGNORECASE),
        re.compile(r"\beval\s*\(", re.IGNORECASE),
        re.compile(r"\bexec\s*\(", re.IGNORECASE),
    ]

    @classmethod
    def mask_pii(cls, text: str) -> str:
        """Mask common PII patterns in free text."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        text = cls.EMAIL_RE.sub("[REDACTED_EMAIL]", text)
        text = cls.ID_RE.sub("[REDACTED_ID]", text)
        text = cls.SSN_RE.sub("[REDACTED_SSN]", text)
        return text

    @classmethod
    def circuit_breaker(cls, ai_output: str) -> bool:
        """
        Naive guard: block obviously dangerous generated code.
        This is a heuristic, not a full security boundary.
        """
        if not isinstance(ai_output, str):
            return False

        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(ai_output):
                print("🛑 SECURITY ALERT: AI attempted unauthorized execution.")
                return False

        return True
