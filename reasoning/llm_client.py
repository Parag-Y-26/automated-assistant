import os
import logging
import json
import time
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self, model_name: str = "meta/llama-3.1-70b-instruct"):
        self.model_name = model_name
        self.api_key = os.getenv("NVIDIA_API_KEY")
        if not self.api_key:
            logging.warning("NVIDIA_API_KEY is not set in the environment logs. API calls will fail.")
            
        self.base_url = "https://integrate.api.nvidia.com/v1"
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        logging.info(f"LLMClient initialized using NVIDIA NIM API (Model: {self.model_name})")

    def generate_json(self, prompt: str, schema: dict = None, max_tokens: int = 1024, temperature: float = 0.1) -> dict:
        """
        Generates a JSON response from the LLM via NVIDIA NIM API.
        """
        try:
            # NVIDIA NIM API supports response_format={"type": "json_object"} natively for many models
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                stop=["</action>", "</plan>", "</intent>"]
            )
            
            text = response.choices[0].message.content
            return json.loads(text)
             
        except Exception as e:
             logging.error("LLM JSON generation failed via NVIDIA NIM: %s", e)
             raise
             
    def generate_text(self, prompt: str, max_tokens: int = 512, temperature: float = 0.3) -> str:
        """Generates raw text via NVIDIA NIM API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
             logging.error("LLM text generation failed via NVIDIA NIM: %s", e)
             raise
