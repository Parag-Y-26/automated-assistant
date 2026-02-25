import os
import logging
from reasoning.llm_client import LLMClient
from state.fsm import StateTracker

logger = logging.getLogger("ladas.parser")

class InstructionParser:
    def __init__(self, llm_client: LLMClient, config: dict):
        self.llm = llm_client
        self.config = config
        
        # Load prompt template
        template_path = os.path.join(os.path.dirname(__file__), 'prompt_templates', 'system_parsing.txt')
        with open(template_path, 'r') as f:
            self.system_prompt = f.read()

    def parse(self, instruction: str, state: StateTracker) -> dict:
        """Parse raw text into structured task intent JSON."""
        max_calls = self.config.get("reasoning", {}).get("max_llm_calls_per_task", 20)
        
        if state.llm_call_count >= max_calls:
            logger.warning(f"Max LLM calls ({max_calls}) reached. Using fallback intent.")
            return {"task_id": state.task_id, "parsed_goal": instruction, "llm_fallback": True}
            
        prompt = self.system_prompt.replace("{instruction}", instruction)
        state.llm_call_count += 1
        
        try:
            # Call LLM to generate JSON
            intent_json = self.llm.generate_json(prompt)
            # Validate schema (in a full implementation, use Pydantic here)
            return intent_json
        except Exception as e:
            logger.exception("LLM generation failed during parsing. Using fallback intent.")
            return {"task_id": state.task_id, "parsed_goal": instruction, "llm_fallback": True}
