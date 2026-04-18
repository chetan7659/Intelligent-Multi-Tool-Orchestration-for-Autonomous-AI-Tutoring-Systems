"""LLM client — uses Groq API (OpenAI-compatible, free tier, no firewall issues)."""
import json
import re
from typing import Any, Dict, Optional
import httpx
from app.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class HuggingFaceLLMClient:
    """
    LLM client backed by Groq (free tier).
    Groq supports Llama-3.1-70B-Versatile with very low latency and no firewall issues.
    API is OpenAI-compatible — just needs GROQ_API_KEY in .env.
    """

    def __init__(self):
        self.groq_token = settings.GROQ_API_KEY
        self.groq_model = settings.GROQ_MODEL   # e.g. llama-3.1-70b-versatile

    async def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.3) -> str:
        """Generate text using Groq API."""
        if not self.groq_token:
            return self._mock_response(prompt)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.groq_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.groq_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": False,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                print(f"Groq API {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"Groq API error: {e}")

        return self._mock_response(prompt)

    def _mock_response(self, prompt: str) -> str:
        """Fallback mock when Groq API key is not set or call fails."""
        if "Return ONLY valid JSON" in prompt or '"topic"' in prompt:
            return '{"mock": true}'
        return "Please configure GROQ_API_KEY in .env to enable AI-powered responses."

    async def extract_json(self, prompt: str) -> Dict[str, Any]:
        """Generate and parse JSON from LLM."""
        raw = await self.generate(prompt)
        try:
            # Clean possible markdown wrap from 70B output
            clean_raw = raw.replace("```json", "").replace("```", "").strip()
            m = re.search(r'\{.*\}', clean_raw, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception:
            pass
        return {"raw_response": raw}

    async def classify(self, text: str, labels: list) -> Dict[str, float]:
        """Zero-shot classification via Groq prompt."""
        label_list = ", ".join(labels)
        prompt = (
            f'Classify the following text into exactly one of these categories: {label_list}\n'
            f'Text: "{text}"\n'
            f'Respond with ONLY a JSON object mapping each label to a confidence score (0.0-1.0) that sums to 1.\n'
            f'Example: {{"label1": 0.8, "label2": 0.2}}'
        )
        try:
            result = await self.extract_json(prompt)
            if isinstance(result, dict) and all(label in result for label in labels):
                return {label: float(result.get(label, 0)) for label in labels}
        except Exception:
            pass
        return {label: 1.0 / len(labels) for label in labels}


# Singleton
_llm_client: Optional[HuggingFaceLLMClient] = None


def get_llm_client() -> HuggingFaceLLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = HuggingFaceLLMClient()
    return _llm_client
