import os
import json
import logging
from reasoning.llm_client import LLMClient
from state.fsm import StateTracker

logger = logging.getLogger("ladas.decision")

class DecisionEngine:
    def __init__(self, llm_client: LLMClient, config: dict):
        self.llm = llm_client
        self.config = config
        
        # Load prompt template
        template_path = os.path.join(
             os.path.dirname(__file__), 'prompt_templates', 'system_action.txt')
        with open(template_path, 'r') as f:
            self.system_prompt = f.read()

    def get_next_action(self, 
                        intent: dict,
                        current_step: dict, 
                        step_idx: int, 
                        total_steps: int, 
                        screen_state: dict, 
                        context_history: list,
                        state: StateTracker) -> dict:
        """Determines the next action based on current state and step."""
        max_calls = self.config.get("reasoning", {}).get("max_llm_calls_per_task", 20)
        
        fallback_action = {
            "action_type": "wait",
            "parameters": {"duration_ms": 2000},
            "reasoning": "Fallback to wait due to LLM limit/error.",
            "llm_fallback": True
        }
        
        if state.llm_call_count >= max_calls:
            logger.warning(f"Max LLM calls ({max_calls}) reached. Using fallback action.")
            return fallback_action
            
        prompt = self.system_prompt.replace("{goal}", intent.get("parsed_goal", "Unknown Goal"))\
                                   .replace("{current_step_idx}", str(step_idx + 1))\
                                   .replace("{total_steps}", str(total_steps))\
                                   .replace("{step_description}", current_step.get("description", "Unknown"))\
                                   .replace("{screen_state_json}", json.dumps(screen_state, indent=2))\
                                   .replace("{context_history}", json.dumps(context_history, indent=2))
                                   
        # Optional: Rule-based fast-paths can go here before calling the LLM
        # e.g., if step is "wait_for_download" and loading indicator is present, return {"action_type": "wait"}
        
        state.llm_call_count += 1
        
        try:
            accion_json = self.llm.generate_json(prompt)
            return accion_json
        except Exception as e:
            logger.exception("LLM generation failed during decision. Using fallback action.")
            return fallback_action
