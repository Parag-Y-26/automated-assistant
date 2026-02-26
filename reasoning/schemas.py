from typing import Optional, List, Dict, Union, Any
from pydantic import BaseModel, Field, field_validator

class TargetBBox(BaseModel):
    bbox: List[int] = Field(..., description="Bounding box [x1, y1, x2, y2]")
    
    @field_validator('bbox')
    def check_bbox_length(cls, v):
        if len(v) != 4:
            raise ValueError('bbox must have exactly 4 elements: [x1, y1, x2, y2]')
        return v

class Coordinates(BaseModel):
    x: int
    y: int

class ActionParameters(BaseModel):
    # Depending on the action type, these fields may or may not be present
    button: Optional[str] = Field("left", description="Mouse button (left, right, middle)")
    start_coords: Optional[Coordinates] = None
    end_coords: Optional[Coordinates] = None
    amount: Optional[int] = Field(None, description="Scroll amount")
    text: Optional[str] = Field(None, description="Text to type")
    clear_first: Optional[bool] = Field(False, description="Clear text field before typing")
    key: Optional[str] = Field(None, description="Key to press")
    keys: Optional[List[str]] = Field(None, description="List of keys for hotkey combo")
    duration_ms: Optional[int] = Field(1000, description="Duration in milliseconds for wait action")
    command: Optional[str] = Field(None, description="Terminal command to execute")
    target: Optional[TargetBBox] = None
    
    # Catch-all for extra params not rigidly typed
    model_config = {
        "extra": "allow"
    }

class ActionCommand(BaseModel):
    action_type: str = Field(..., description="Type of action (e.g., click, move, type_text, wait, run_command)")
    parameters: ActionParameters = Field(default_factory=ActionParameters)
    reasoning: str = Field("", description="Reasoning for choosing this action")
    coordinates: Optional[Coordinates] = None
    pre_action_wait_ms: int = Field(0, description="Wait time before executing action")
    post_action_wait_ms: int = Field(500, description="Wait time after executing action")
    
    @field_validator('action_type')
    def validate_action_type(cls, v):
        allowed = {"click", "double_click", "right_click", "move", "scroll", "drag", 
                   "type_text", "press_key", "hotkey", "wait", "run_command", "screenshot",
                   "search_web"} # search_web added for Phase 2 integration
        normalized = v.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"Action type '{normalized}' is not one of {allowed}")
        return normalized
