import os
from reasoning.llm_client import LLMClient

class InstructionParser:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        
        # Load prompt template
        template_path = os.path.join(os.path.dirname(__file__), 'prompt_templates', 'system_parsing.txt')
        with open(template_path, 'r') as f:
            self.system_prompt = f.read()

    def parse(self, instruction: str) -> dict:
        """Parse raw text into structured task intent JSON."""
        prompt = self.system_prompt.replace("{instruction}", instruction)
        
        # Call LLM to generate JSON
        intent_json = self.llm.generate_json(prompt)
        
        # Validate schema (in a full implementation, use Pydantic here)
        return intent_json
