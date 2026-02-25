import os
import json
import logging
from reasoning.llm_client import LLMClient
from state.fsm import StateTracker

logger = logging.getLogger("ladas.planner")

class TaskPlanner:
    def __init__(self, llm_client: LLMClient, config: dict):
        self.llm = llm_client
        self.config = config
        
        # Load prompt template
        template_path = os.path.join(
             os.path.dirname(__file__), '..', 'reasoning', 'prompt_templates', 'system_planning.txt')
        with open(template_path, 'r') as f:
            self.system_prompt = f.read()

    def generate_plan(self, intent_json: dict, state: StateTracker, screen_summary: dict = None) -> dict:
        """Generate a structured step plan from a task intent."""
        max_calls = self.config.get("reasoning", {}).get("max_llm_calls_per_task", 20)
        fallback_plan = {
            "steps": [{"step_id": "fallback_1", "description": intent_json.get("parsed_goal", "execute command"), "max_retries": 1}],
            "llm_fallback": True
        }
        
        if state.llm_call_count >= max_calls:
            logger.warning(f"Max LLM calls ({max_calls}) reached. Using fallback plan.")
            return fallback_plan
            
        intent_str = json.dumps(intent_json, indent=2)
        screen_str = json.dumps(screen_summary, indent=2) if screen_summary else "No current screen state available."
        
        prompt = self.system_prompt.replace("{intent_json}", intent_str)\
                                   .replace("{screen_summary}", screen_str)
        
        state.llm_call_count += 1
        
        try:
            # Call LLM to generate JSON
            plan_json = self.llm.generate_json(prompt)
            logger.info(f"Generated plan JSON: {json.dumps(plan_json, indent=2)}")
            # Minimal validation or default injection could happen here
            return plan_json
        except Exception as e:
            logger.exception("LLM generation failed during planning. Using fallback plan.")
            return fallback_plan
