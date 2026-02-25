import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class TaskRecord(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, unique=True, nullable=False)
    session_id = Column(String, nullable=False)
    raw_instruction = Column(Text, nullable=False)
    parsed_goal = Column(Text, nullable=True)
    status = Column(String, default="PENDING") # PENDING, IN_PROGRESS, COMPLETED, FAILED, ABORTED
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    plan_json = Column(Text, nullable=True)

class StepRecord(Base):
    __tablename__ = 'steps'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False)
    step_id = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="PENDING") # PENDING, COMPLETED, FAILED
    retry_count = Column(Integer, default=0)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)

class ActionLogRecord(Base):
    __tablename__ = 'action_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    task_id = Column(String, nullable=False)
    step_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    action_type = Column(String, nullable=False)
    reasoning = Column(Text, nullable=True)
    screen_hash_before = Column(String, nullable=True)
    
class Database:
    def __init__(self, db_path: str = "ladas_memory.db"):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
    def get_session(self):
        return self.Session()
