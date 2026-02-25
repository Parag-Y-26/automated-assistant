import json
import logging
from datetime import datetime
from memory.database import Database, ActionLogRecord

class ActionLog:
    """Append-only log for recording all actions executed by the agent."""
    def __init__(self, db: Database):
        self.db = db

    def log_action(self, 
                   session_id: str, 
                   task_id: str, 
                   step_id: str, 
                   action_cmd: dict, 
                   screen_hash_before: str):
        """Record an executed action."""
        session = self.db.get_session()
        try:
            action_type = action_cmd.get("action_type", "unknown")
            reasoning = action_cmd.get("reasoning", "")
            
            record = ActionLogRecord(
                session_id=session_id,
                task_id=task_id,
                step_id=step_id,
                action_type=action_type,
                reasoning=reasoning,
                screen_hash_before=screen_hash_before
            )
            session.add(record)
            session.commit()
            
            # Also write to structured JSONL file for observability
            self._write_to_jsonl(session_id, {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "session_id": session_id,
                "task_id": task_id,
                "step_id": step_id,
                "action_cmd": action_cmd,
                "screen_hash_before": screen_hash_before
            })
            
        except Exception as e:
            logging.error(f"Failed to log action: {e}")
            session.rollback()
        finally:
            session.close()

    def _write_to_jsonl(self, session_id: str, data: dict):
        """Append to a session-specific JSONL file."""
        import os
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        file_path = os.path.join(log_dir, f"session_{session_id}.jsonl")
        
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")
        except IOError as e:
            logging.error(f"Could not write to JSONL log: {e}")
            
    def get_recent_actions(self, task_id: str, limit: int = 10) -> list:
        """Retrieve recent actions for context building."""
        session = self.db.get_session()
        actions = []
        try:
            records = session.query(ActionLogRecord)\
                             .filter_by(task_id=task_id)\
                             .order_by(ActionLogRecord.timestamp.desc())\
                             .limit(limit)\
                             .all()
                             
            for r in reversed(records): # Return chronological order
                actions.append({
                    "step_id": r.step_id,
                    "action_type": r.action_type,
                    "reasoning": r.reasoning
                })
        finally:
            session.close()
        return actions
