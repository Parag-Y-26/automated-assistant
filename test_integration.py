import unittest
import json
from unittest.mock import MagicMock
from state.fsm import StateTracker
from planning.task_planner import TaskPlanner
from reasoning.decision_engine import DecisionEngine
from reasoning.instruction_parser import InstructionParser

class MockLLMClient:
    def __init__(self):
        self.responses = []

    def set_responses(self, responses):
        self.responses = responses

    def generate_json(self, prompt: str) -> dict:
        if self.responses:
            return self.responses.pop(0)
        return {}
        
class TestIntegrationPipeline(unittest.TestCase):
    def setUp(self):
        self.config = {
            "reasoning": {
                "max_llm_calls_per_task": 20
            }
        }
        self.llm = MockLLMClient()
        self.parser = InstructionParser(self.llm, self.config)
        self.planner = TaskPlanner(self.llm, self.config)
        self.decision = DecisionEngine(self.llm, self.config)
        
        self.state = StateTracker()
        self.state.task_id = "test_task_1"
        
    def test_pipeline_success(self):
        # 1. Setup mock LLM responses
        expected_intent = {
            "task_id": "test_task_1",
            "parsed_goal": "Click the OK button",
            "required_apps": []
        }
        expected_plan = {
            "steps": [
                {"step_id": "step_1", "description": "Locate and click the OK button on the screen", "max_retries": 2}
            ]
        }
        expected_action = {
            "action_type": "click",
            "parameters": {
                "target": {
                    "type": "element",
                    "id": "button_ok",
                    "bbox": [100, 100, 150, 120]
                }
            },
            "reasoning": "Found OK button in OCR, proceeding to click."
        }
        
        self.llm.set_responses([expected_intent, expected_plan, expected_action])
        
        # 2. Parse Instruction
        intent = self.parser.parse("Click the OK button", self.state)
        self.assertEqual(intent, expected_intent)
        self.assertEqual(self.state.llm_call_count, 1)
        
        # 3. Generate Plan
        plan = self.planner.generate_plan(intent, self.state)
        self.assertEqual(plan, expected_plan)
        self.assertEqual(self.state.llm_call_count, 2)
        
        self.state.plan = plan
        self.state.advance_step()
        
        # 4. Action Decision
        mock_screen_state = {
            "ocr_elements": [{"text": "OK", "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 20}}],
            "vision_elements": []
        }
        
        action = self.decision.get_next_action(
            intent, 
            self.state.get_current_step(), 
            self.state.current_step_idx, 
            len(self.state.plan["steps"]), 
            mock_screen_state, 
            [], 
            self.state
        )
        
        self.assertEqual(action, expected_action)
        self.assertEqual(self.state.llm_call_count, 3)

    def test_pipeline_fallback(self):
        # Set max calls to 1 so the planner hits the fallback
        self.config["reasoning"]["max_llm_calls_per_task"] = 1
        
        self.llm.set_responses([{"task_id": "test_task_1", "parsed_goal": "test"}])
        
        intent = self.parser.parse("test", self.state)
        self.assertEqual(self.state.llm_call_count, 1)
        
        # This should trigger fallback
        plan = self.planner.generate_plan(intent, self.state)
        self.assertTrue(plan.get("llm_fallback"))
        self.assertEqual(self.state.llm_call_count, 1) # count shouldn't increment

if __name__ == '__main__':
    unittest.main()
