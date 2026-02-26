import asyncio
import logging
import json
import uuid
import time
from typing import Dict, Any, List
# Assume LLMClient provides a generate_json method hitting the local Ollama API
from reasoning.llm_client import LLMClient

logger = logging.getLogger("ladas.tools.compare")

class ModelComparisonModule:
    """
    Vertex AI Studio-inspired "Compare" feature to benchmark two Ollama models locally.
    Routes exclusively through the local Ollama API. No external providers (OpenRouter/Groq).
    Outputs a structured side-by-side diff of reasoning logs and plans.
    """
    def __init__(self, model_a: str, model_b: str):
        self.model_a_name = model_a
        self.model_b_name = model_b
        # Instantiate separate clients referencing the local Ollama backend
        self.client_a = LLMClient(model_path=model_a)
        self.client_b = LLMClient(model_path=model_b)
        
        # Override the defaults purely for this benchmarking session
        self.client_a.model_name = model_a
        self.client_b.model_name = model_b

    def generate_plan_sync(self, client: LLMClient, prompt: str) -> Dict[str, Any]:
        """Wrapper to call the generation synchronously (or run inside run_in_executor)"""
        start = time.time()
        try:
            response = client.generate_json(prompt, max_tokens=1500)
            latency = time.time() - start
            return {
                "success": True,
                "latency_sec": round(latency, 2),
                "plan": response
            }
        except Exception as e:
            latency = time.time() - start
            return {
                "success": False,
                "latency_sec": round(latency, 2),
                "error": str(e)
            }

    async def compare_plans(self, intent_prompt: str) -> Dict[str, Any]:
        """
        Executes the exact same prompt concurrently on both specified local models
        and returns a side-by-side analysis dictionary.
        """
        logger.info(f"Running side-by-side evaluation: Model A ({self.model_a_name}) vs Model B ({self.model_b_name})")
        
        # Run synchronous calls concurrently using threads
        loop = asyncio.get_running_loop()
        
        # Future 1
        task_a = loop.run_in_executor(
            None, 
            self.generate_plan_sync, 
            self.client_a, 
            intent_prompt
        )
        
        # Future 2
        task_b = loop.run_in_executor(
            None, 
            self.generate_plan_sync, 
            self.client_b, 
            intent_prompt
        )
        
        # Await concurrently
        res_a, res_b = await asyncio.gather(task_a, task_b)
        
        # Build Diff structure
        comparison_report = {
            "evaluation_id": str(uuid.uuid4()),
            "prompt": intent_prompt,
            "models": {
                "model_a": {
                    "config": self.model_a_name,
                    "metrics": {
                        "success": res_a["success"],
                        "latency_sec": res_a["latency_sec"]
                    },
                    "output": res_a.get("plan") or res_a.get("error")
                },
                "model_b": {
                    "config": self.model_b_name,
                    "metrics": {
                        "success": res_b["success"],
                        "latency_sec": res_b["latency_sec"]
                    },
                    "output": res_b.get("plan") or res_b.get("error")
                }
            },
            "system_recommendation": self._generate_recommendation(res_a, res_b)
        }
        
        return comparison_report

    def _generate_recommendation(self, res_a: dict, res_b: dict) -> str:
        """Internal heuristic to identify the winning model for the benchmark"""
        if not res_a["success"] and not res_b["success"]:
            return "Both models failed to parse structured output."
        if res_a["success"] and not res_b["success"]:
            return f"Model A '{self.model_a_name}' recommended (Model B failed JSON generation/parsing)."
        if res_b["success"] and not res_a["success"]:
            return f"Model B '{self.model_b_name}' recommended (Model A failed JSON generation/parsing)."
            
        # Both succeeded; compare latency or plan complexity
        diff_ms = res_a["latency_sec"] - res_b["latency_sec"]
        faster_model = self.model_a_name if diff_ms < 0 else self.model_b_name
        
        return f"Both succeeded. {faster_model} was faster by {abs(round(diff_ms, 2))} seconds."
