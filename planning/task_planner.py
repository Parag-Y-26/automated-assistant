import os
import json
from reasoning.llm_client import LLMClient

class TaskPlanner:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        
        # Load prompt template
        template_path = os.path.join(
             os.path.dirname(__file__), '..', 'reasoning', 'prompt_templates', 'system_planning.txt')
        with open(template_path, 'r') as f:
            self.system_prompt = f.read()

    def generate_plan(self, intent_json: dict, screen_summary: dict = None) -> dict:
        """Generate a structured step plan from a task intent."""
        intent_str = json.dumps(intent_json, indent=2)
        screen_str = json.dumps(screen_summary, indent=2) if screen_summary else "No current screen state available."
        
        prompt = self.system_prompt.replace("{intent_json}", intent_str)\
                                   .replace("{screen_summary}", screen_str)
        
        # Call LLM to generate JSON
        plan_json = self.llm.generate_json(prompt)
        
        # Minimal validation or default injection could happen here
        return plan_json
