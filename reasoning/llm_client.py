import logging
import json
import requests
import re

class LLMClient:
    def __init__(self, model_path: str, n_ctx: int = 4096, n_gpu_layers: int = -1):
        # We ignore model_path and use ollama's phi3 to bypass C++ build issues on Windows
        self.model_name = "phi3"
        self.ollama_url = "http://localhost:11434/api/generate"
        logging.info(f"LLMClient initialized using local Ollama API (Model: {self.model_name})")

    def generate_json(self, prompt: str, schema: dict = None, max_tokens: int = 1024, temperature: float = 0.1) -> dict:
        """
        Generates a JSON response from the LLM via Ollama API.
        """
        try:
             payload = {
                 "model": self.model_name,
                 "prompt": prompt,
                 "stream": False,
                 "options": {
                     "temperature": temperature,
                     "num_predict": max_tokens,
                     "stop": ["</action>", "</plan>", "</intent>"]
                 }
             }
             if schema:
                 payload["format"] = "json"
                 
             response = requests.post(self.ollama_url, json=payload, timeout=120)
             response.raise_for_status()
             result = response.json()
             text = result.get("response", "")
             
             # Extract json by taking the first { and the last }
             start = text.find('{')
             end = text.rfind('}')
             if start != -1 and end != -1 and start < end:
                 json_str = text[start:end+1]
                 json_str = re.sub(r',\s*\}', '}', json_str)
                 json_str = re.sub(r',\s*\]', ']', json_str)
                 try:
                     return json.loads(json_str)
                 except json.JSONDecodeError as e:
                     # Attempt to find an earlier closing brace in case of trailing text
                     # e.g., {"a":1} Some extra words here}
                     for i in range(end - 1, start, -1):
                         if text[i] == '}':
                             try:
                                 return json.loads(text[start:i+1])
                             except json.JSONDecodeError:
                                 continue
                     raise ValueError(f"Extracted json string was invalid: {e}\nRaw extracted string was:\n{json_str}")
             
             raise ValueError("Could not extract JSON from LLM response.")
             
        except Exception as e:
             logging.error(f"LLM JSON generation failed: {e}")
             raise
             
    def generate_text(self, prompt: str, max_tokens: int = 512, temperature: float = 0.3) -> str:
        """Generates raw text (e.g. for context summarization) via Ollama API."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        res = requests.post(self.ollama_url, json=payload, timeout=120)
        res.raise_for_status()
        return res.json().get("response", "").strip()
