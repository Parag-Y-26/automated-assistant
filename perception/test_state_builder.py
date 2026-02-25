import unittest
import json
from perception.state_builder import StateBuilder

class TestStateBuilder(unittest.TestCase):
    def test_build_screen_state(self):
        # Mock OCR Data
        ocr_data = [
            {"text": "Login", "bounding_box": {"x": 100, "y": 200, "width": 50, "height": 20}},
            {"text": "System Error Detected", "bounding_box": {"x": 50, "y": 50, "width": 200, "height": 30}}
        ]
        
        # Mock Vision Data
        vision_data = [
            {"class": "button", "center": {"x": 125, "y": 210}, "bounding_box": {"x": 90, "y": 190, "width": 70, "height": 40}},
            {"class": "spinner", "center": {"x": 500, "y": 500}, "bounding_box": {"x": 490, "y": 490, "width": 20, "height": 20}}
        ]
        
        state = StateBuilder.build_screen_state(
            session_id="test_sess",
            step_id="step_1",
            monitor_index=0,
            region=None,
            screens_dims=(1920, 1080),
            screen_hash="abcdef123456",
            ocr_elements=ocr_data,
            vision_elements=vision_data
        )
        
        # Verify basic structure
        self.assertEqual(state["session_id"], "test_sess")
        self.assertEqual(state["screen_dimensions"]["width"], 1920)
        self.assertTrue(state["error_dialogs_detected"])
        self.assertTrue(state["loading_indicators_detected"])
        
        # Verify naive OCR->Vision assignment heuristic
        button_element = next(v for v in state["vision_elements"] if v["class"] == "button")
        self.assertEqual(button_element.get("label"), "Login", "OCR text should be assigned to nearby vision box")

if __name__ == '__main__':
    unittest.main()
