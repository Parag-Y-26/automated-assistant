import os
import json
from reasoning.llm_client import LLMClient

class DecisionEngine:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        
        # Load prompt template
        template_path = os.path.join(
             os.path.dirname(__file__), 'prompt_templates', 'system_action.txt')
        with open(template_path, 'r') as f:
            self.system_prompt = f.read()

    def get_next_action(self, 
                        current_step: dict, 
                        step_idx: int, 
                        total_steps: int, 
                        screen_state: dict, 
                        context_history: list) -> dict:
        """Determines the next action based on current state and step."""
        
        prompt = self.system_prompt.replace("{current_step_idx}", str(step_idx + 1))\
                                   .replace("{total_steps}", str(total_steps))\
                                   .replace("{step_description}", current_step.get("description", "Unknown"))\
                                   .replace("{screen_state_json}", json.dumps(screen_state, indent=2))\
                                   .replace("{context_history}", json.dumps(context_history, indent=2))
                                   
        # Optional: Rule-based fast-paths can go here before calling the LLM
        # e.g., if step is "wait_for_download" and loading indicator is present, return {"action_type": "wait"}
        
        accion_json = self.llm.generate_json(prompt)
        
        return accion_json
