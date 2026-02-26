import asyncio
import logging
import json
import uuid
import time
from typing import Dict, Any, List
from reasoning.llm_client import LLMClient

logger = logging.getLogger("ladas.tools.compare")

class ModelComparisonModule:
    """
    Vertex AI Studio-inspired "Compare" feature for NVIDIA NIM.
    Executes tasks concurrently across two different NVIDIA endpoints.
    Tracks Time to First Token (TTFT), Tokens Per Second (TPS), and latency.
    """
    def __init__(self, model_a: str, model_b: str):
        self.model_a_name = model_a
        self.model_b_name = model_b
        
        self.client_a = LLMClient(model_name=model_a)
        self.client_b = LLMClient(model_name=model_b)

    async def generate_plan_async(self, client: LLMClient, prompt: str) -> Dict[str, Any]:
        """Async generation to track TTFT and TPS via streaming API"""
        start_time = time.time()
        ttft = None
        full_text = ""
        token_count = 0
        
        try:
            # Use the underlying OpenAI async client for streaming to capture TTFT
            import os
            from openai import AsyncOpenAI
            
            async_client = AsyncOpenAI(
                api_key=os.getenv("NVIDIA_API_KEY"),
                base_url="https://integrate.api.nvidia.com/v1"
            )
            
            stream = await async_client.chat.completions.create(
                model=client.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.1,
                stream=True
            )
            
            async for chunk in stream:
                if ttft is None:
                    ttft = time.time() - start_time
                if chunk.choices and chunk.choices[0].delta.content:
                    full_text += chunk.choices[0].delta.content
                    # Rough estimate of tokens (NVIDIA NIM provides usage in stream typically, but we proxy by chunk)
                    token_count += 1 

            total_latency = time.time() - start_time
            tps = token_count / total_latency if total_latency > 0 else 0
            
            # Attempt to parse json
            try:
                # Find valid JSON bounds in stream buffer
                start_idx = full_text.find('{')
                end_idx = full_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = full_text[start_idx:end_idx+1]
                    parsed_plan = json.loads(json_str)
                else:
                    parsed_plan = json.loads(full_text)
            except json.JSONDecodeError as e:
                parsed_plan = {"error": "Invalid format", "raw_output": full_text}
                
            return {
                "success": "error" not in parsed_plan,
                "latency_sec": round(total_latency, 2),
                "ttft_sec": round(ttft if ttft else total_latency, 2),
                "tps": round(tps, 2),
                "plan": parsed_plan
            }
            
        except Exception as e:
            total_latency = time.time() - start_time
            return {
                "success": False,
                "latency_sec": round(total_latency, 2),
                "ttft_sec": 0,
                "tps": 0,
                "error": str(e)
            }

    async def compare_plans(self, intent_prompt: str) -> Dict[str, Any]:
        """
        Executes the prompt concurrently on both specified NIM models
        and returns a side-by-side analysis dictionary.
        """
        logger.info(f"Running side-by-side evaluation: Model A ({self.model_a_name}) vs Model B ({self.model_b_name})")
        
        # Await concurrently
        res_a, res_b = await asyncio.gather(
            self.generate_plan_async(self.client_a, intent_prompt),
            self.generate_plan_async(self.client_b, intent_prompt)
        )
        
        # Build Diff structure
        comparison_report = {
            "evaluation_id": str(uuid.uuid4()),
            "prompt": intent_prompt,
            "models": {
                "model_a": {
                    "config": self.model_a_name,
                    "metrics": {
                        "success": res_a["success"],
                        "latency_sec": res_a["latency_sec"],
                        "ttft_sec": res_a["ttft_sec"],
                        "tps": res_a["tps"]
                    },
                    "output": res_a.get("plan") or res_a.get("error")
                },
                "model_b": {
                    "config": self.model_b_name,
                    "metrics": {
                        "success": res_b["success"],
                        "latency_sec": res_b["latency_sec"],
                        "ttft_sec": res_b["ttft_sec"],
                        "tps": res_b["tps"]
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
