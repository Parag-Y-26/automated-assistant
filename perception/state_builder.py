from datetime import datetime
from typing import Dict, Any, List

class StateBuilder:
    """Builds the unified ScreenState JSON object from OCR and Vision detections."""
    
    @staticmethod
    def build_screen_state(
        session_id: str,
        step_id: str,
        monitor_index: int,
        region: list,
        screens_dims: tuple,
        screen_hash: str,
        ocr_elements: List[Dict[str, Any]],
        vision_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        
        # Determine if loading indicators or error dialogues are present
        # This is a naive check; ideally the vision model distinguishes these classes specifically.
        loading_detected = any(v.get("class") in ["spinner", "progress_bar"] for v in vision_elements)
        error_detected = any("error" in o.get("text", "").lower() for o in ocr_elements)
        
        # Enrich vision elements with nearby OCR text where applicable
        # (Naive: if the centers are close, assign the OCR text as the label)
        for v in vision_elements:
             v_center = v.get("center", {})
             vx, vy = v_center.get("x", 0), v_center.get("y", 0)
             
             for o in ocr_elements:
                  o_bbox = o.get("bounding_box", {})
                  ox = o_bbox.get("x", 0) + o_bbox.get("width", 0) // 2
                  oy = o_bbox.get("y", 0) + o_bbox.get("height", 0) // 2
                  
                  # Distance check (naive heuristic: within 50 pixels)
                  dist = ((vx - ox) ** 2 + (vy - oy) ** 2) ** 0.5
                  
                  if dist < 50:
                       # Assign OCR text to the visual element label
                       v["label"] = o["text"]
                       break

        state = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "step_id": step_id,
            "monitor": monitor_index,
            "capture_region": region,
            "screen_dimensions": {
                "width": screens_dims[0],
                "height": screens_dims[1]
            },
            "screen_hash": screen_hash,
            "ocr_elements": ocr_elements,
            "vision_elements": vision_elements,
            # Active Window would require pywin32 or similar OS-level package, 
            # omitted for pure vision approach or mocked for now.
            "active_window": {
                "title": "Unknown",
                "process": "unknown",
                "bounding_box": {"x": 0, "y": 0, "width": screens_dims[0], "height": screens_dims[1]}
            },
            "loading_indicators_detected": loading_detected,
            "error_dialogs_detected": error_detected
        }
        
        return state
