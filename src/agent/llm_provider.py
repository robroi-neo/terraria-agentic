
import re
import time
import logging
import requests
import ollama
from config import OLLAMA_MODEL, GROQ_MODEL, IS_DEVELOPMENT, GROQ_API_KEY

# Very Hackish, idk too lazy to use langchain
class LLMProvider:
    def __init__(self, model_name: str = OLLAMA_MODEL, temperature: float = 0.1):
        self.is_development = IS_DEVELOPMENT
        if self.is_development:
            self.model_name = model_name
        else:
            self.model_name = GROQ_MODEL
        self.temperature = temperature


    def complete(self, system: str, user: str, retries: int = 3) -> str:
        if self.is_development:
            for attempt in range(retries):
                try:
                    logging.info(f"[DEV] Using Ollama model: {self.model_name}")
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
        else:
            # Use Groq API in production
            logging.info("[PROD] Using Groq API for LLM completion.")
            api_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                "temperature": self.temperature
            }
            for attempt in range(retries):
                response = requests.post(api_url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    return self._clean_json(content)
                elif response.status_code == 429 and attempt < retries - 1:
                    wait = 60
                    logging.warning(f"Groq API rate limited. Waiting {wait}s before retry {attempt + 1}/{retries}...")
                    time.sleep(wait)
                else:
                    logging.error(f"Groq API error: {response.status_code} {response.text}")
                    raise Exception(f"Groq API error: {response.status_code} {response.text}")

    def _clean_json(self, text: str) -> str:
        # Prefer fenced code block if present
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Otherwise, try to extract the first {...} JSON object
        brace_match = re.search(r"\{[\s\S]*?\}", text)
        if brace_match:
            return brace_match.group(0).strip()

        # Fallback: return original text (may still error downstream)
        return text.strip()