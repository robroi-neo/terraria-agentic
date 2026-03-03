import re
import time
import logging
import ollama
from config import OLLAMA_MODEL

class LLMProvider:
    def __init__(self, model_name: str = OLLAMA_MODEL, temperature: float = 0.2):
        self.model_name = model_name
        self.temperature = temperature

    def complete(self, system: str, user: str, retries: int = 3) -> str:
        for attempt in range(retries):
            try:
                logging.info(f"Using Ollama model: {self.model_name}")
                response = ollama.chat(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    options={"temperature": self.temperature}
                )
                return self._clean_json(response["message"]["content"])
            except Exception as e:
                if "429" in str(e) and attempt < retries - 1:
                    wait = 60
                    logging.warning(f"Rate limited. Waiting {wait}s before retry {attempt + 1}/{retries}...")
                    time.sleep(wait)
                else:
                    raise

    def _clean_json(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()