import re
import time
import logging
import google.generativeai as genai
from config import GEMINI_MODEL, GEMINI_API_KEY

class LLMProvider:
    def __init__(self, model_name: str = GEMINI_MODEL, temperature: float = 0.2):
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None

    def get_llm(self):
        if self._llm is None:
            if not GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not set.")
            logging.info(f"Initializing Gemini: {self.model_name}")
            genai.configure(api_key=GEMINI_API_KEY)
            self._llm = genai.GenerativeModel(self.model_name)
        return self._llm

    def complete(self, system: str, user: str, retries: int = 3) -> str:
        llm = self.get_llm()
        prompt = f"{system}\n\nUser: {user}"

        for attempt in range(retries):
            try:
                response = llm.generate_content(prompt)
                return self._clean_json(response.text)
            except Exception as e:
                if "429" in str(e) and attempt < retries - 1:
                    wait = 60   # wait 60 seconds before retrying
                    logging.warning(f"Rate limited. Waiting {wait}s before retry {attempt + 1}/{retries}...")
                    time.sleep(wait)
                else:
                    raise

    def _clean_json(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()