import os
from dotenv import load_dotenv
from pydantic_ai import Agent

load_dotenv()


class MarcelArchEngine:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")

        self.auditor_agent = Agent(
            "openai:gpt-4o-mini",
            result_type=AuditResult,
            system_prompt=(
                "You are a forensic contract auditor. Extract vendor name and billing rules "
                "from the provided contract text."
            ),
        )

    async def audit_document(self, raw_contract: str):
        result = await self.auditor_agent.run(raw_contract)
        return result.data
