import os
import logging
from langchain.chat_models import ChatGoogleGenerativeAI  # or ChatGemini if available
from config import GEMINI_MODEL, GEMINI_API_KEY  # Make sure you store API key in config or env

logging.basicConfig(level=logging.INFO)

class LLMProvider:
    """Class to initialize and return a configured LLM instance."""

    def __init__(self, model_name: str = GEMINI_MODEL, temperature: float = 0.2):
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None

    def get_llm(self):
        """Return an initialized LLM instance."""
        if self._llm is None:
            logging.info(f"Initializing LLM: {self.model_name} with temperature {self.temperature}")
            
            # If using Gemini Flash via LangChain wrapper
            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=self.temperature,
                max_output_tokens=1024,  # equivalent to max_tokens
                api_key=GEMINI_API_KEY   # Pass your key explicitly
            )
        return self._llm