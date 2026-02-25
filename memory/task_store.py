import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from memory.database import Database, TaskRecord, StepRecord

class TaskStore:
    def __init__(self, db: Database):
        self.db = db
        
    def create_task(self, session_id: str, task_id: str, instruction: str) -> bool:
        session = self.db.get_session()
        try:
            task = TaskRecord(
                task_id=task_id, 
                session_id=session_id, 
                raw_instruction=instruction
            )
            session.add(task)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def update_task_plan(self, task_id: str, parsed_goal: str, plan_dict: dict):
        session = self.db.get_session()
        try:
            task = session.query(TaskRecord).filter_by(task_id=task_id).first()
            if task:
                task.parsed_goal = parsed_goal
                task.plan_json = json.dumps(plan_dict)
                task.status = "IN_PROGRESS"
                session.commit()
                
                # Create step records
                for step in plan_dict.get("steps", []):
                    step_rec = StepRecord(
                        task_id=task_id,
                        step_id=step["step_id"],
                        description=step["description"]
                    )
                    session.add(step_rec)
                session.commit()
        except:
            session.rollback()
        finally:
            session.close()

    def update_task_status(self, task_id: str, status: str):
        session = self.db.get_session()
        try:
            task = session.query(TaskRecord).filter_by(task_id=task_id).first()
            if task:
                task.status = status
                if status in ["COMPLETED", "FAILED", "ABORTED", "TIMEOUT"]:
                    task.end_time = datetime.utcnow()
                session.commit()
        except:
            session.rollback()
        finally:
            session.close()

    def update_step_status(self, task_id: str, step_id: str, status: str, retries: int = 0):
        session = self.db.get_session()
        try:
            step = session.query(StepRecord).filter_by(task_id=task_id, step_id=step_id).first()
            if step:
                step.status = status
                step.retry_count = retries
                if status in ["COMPLETED", "FAILED"]:
                    step.end_time = datetime.utcnow()
                session.commit()
        except:
            session.rollback()
        finally:
            session.close()
            
    def get_incomplete_tasks(self) -> List[Dict]:
        """Used for crash recovery feature."""
        session = self.db.get_session()
        tasks = []
        try:
            records = session.query(TaskRecord).filter_by(status="IN_PROGRESS").all()
            for r in records:
                tasks.append({
                    "task_id": r.task_id,
                    "session_id": r.session_id,
                    "instruction": r.raw_instruction
                })
        finally:
            session.close()
        return tasks
