import logging
import json

try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False

class LLMClient:
    def __init__(self, model_path: str, n_ctx: int = 4096, n_gpu_layers: int = -1):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.llm = None
        
        if LLAMA_AVAILABLE:
            try:
                logging.info(f"Loading LLM from {model_path} with {n_gpu_layers} GPU layers.")
                self.llm = Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=False
                )
            except Exception as e:
                logging.error(f"Failed to load LLM: {e}")
        else:
            logging.error("llama-cpp-python is not installed.")

    def generate_json(self, prompt: str, schema: dict = None, max_tokens: int = 1024, temperature: float = 0.1) -> dict:
        """
        Generates a JSON response from the LLM. 
        In a real implementation, we would use llama-cpp-python's grammar mapping 
        to strictly enforce JSON output. For simplicity here, we rely on prompt engineering
        and basic parsing.
        """
        if not self.llm:
            raise RuntimeError("LLM not initialized.")
            
        try:
             response = self.llm(
                  prompt,
                  max_tokens=max_tokens,
                  temperature=temperature,
                  stop=["</action>", "</plan>", "</intent>"] # example stops
             )
             
             text = response["choices"][0]["text"]
             
             # Extract json between tags if present (naive parsing)
             import re
             json_match = re.search(r'\{(?:[^{}]|(?R))*\}', text, re.DOTALL) # Basic attempt, regex for complete json is complex
             # Fallback simpler extraction
             start = text.find('{')
             end = text.rfind('}')
             if start != -1 and end != -1:
                  json_str = text[start:end+1]
                  return json.loads(json_str)
             
             raise ValueError("Could not extract JSON from LLM response.")
             
        except Exception as e:
             logging.error(f"LLM JSON generation failed: {e}")
             raise
             
    def generate_text(self, prompt: str, max_tokens: int = 512, temperature: float = 0.3) -> str:
        """Generates raw text (e.g. for context summarization)."""
        if not self.llm:
            raise RuntimeError("LLM not initialized.")
            
        response = self.llm(
             prompt,
             max_tokens=max_tokens,
             temperature=temperature
        )
        return response["choices"][0]["text"].strip()
