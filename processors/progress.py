import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger(__name__)

class ProgressStage(str, Enum):
    UPLOADING = "uploading"
    LOADING_RAW = "loading_raw"
    ANALYZING = "analyzing"
    ENHANCING = "enhancing"
    ENCODING = "encoding"
    COMPLETE = "complete"
    ERROR = "error"

@dataclass
class ProgressState:
    task_id: str
    stage: ProgressStage = ProgressStage.UPLOADING
    percent: int = 0
    message: str = "Starting..."
    created_at: float = field(default_factory=time.time)

class ProgressManager:
    """Thread-safe progress manager for tracking enhancement jobs."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks: Dict[str, ProgressState] = {}
        return cls._instance
    
    def create_task(self, task_id: str) -> ProgressState:
        """Create a new progress tracking task."""
        state = ProgressState(task_id=task_id)
        self._tasks[task_id] = state
        logger.info(f"[{task_id}] Task created")
        return state
    
    def update(self, task_id: str, stage: ProgressStage, percent: int, message: str):
        """Update progress for a task."""
        if task_id in self._tasks:
            self._tasks[task_id].stage = stage
            self._tasks[task_id].percent = percent
            self._tasks[task_id].message = message
            logger.info(f"[{task_id}] {stage.value}: {percent}% - {message}")
    
    def get(self, task_id: str) -> Optional[ProgressState]:
        """Get current progress state for a task."""
        return self._tasks.get(task_id)
    
    def remove(self, task_id: str):
        """Remove a completed task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
    
    def cleanup_old_tasks(self, max_age_seconds: int = 300):
        """Remove tasks older than max_age_seconds."""
        now = time.time()
        to_remove = [
            tid for tid, state in self._tasks.items()
            if now - state.created_at > max_age_seconds
        ]
        for tid in to_remove:
            del self._tasks[tid]

# Global instance
progress_manager = ProgressManager()
