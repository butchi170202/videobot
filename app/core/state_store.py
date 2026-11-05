"""Lightweight in-memory store for personal video settings and active tasks (no DB required)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Optional

from app.core.config import settings
from app.core.constants import TaskStatus


@dataclass
class UserPreferences:
    """Video generation preferences for a Telegram user."""

    model: str = field(default_factory=lambda: settings.DEFAULT_VIDEO_MODEL)
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    duration_seconds: int = 8
    style: str = "cinematic"
    camera_motion: str = "tracking"
    auto_optimize_prompt: bool = True

    def ensure_valid_combination(self) -> Optional[str]:
        """
        Validate parameter constraints enforced by Google Veo 3.1 API.
        For example, 1080p on Veo 3.1 requires an 8-second duration.
        Returns an informational note if an automatic adjustment was made.
        """
        if self.resolution == "1080p" and self.duration_seconds != 8:
            self.duration_seconds = 8
            return "ℹ️ Độ phân giải 1080p trên Veo 3.1 yêu cầu thời lượng 8 giây (đã tự động chuyển sang 8s)."
        return None


@dataclass
class VideoTaskItem:
    """Represents a currently running or recently prepared video generation task in memory."""

    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    user_id: int = 0
    chat_id: int = 0
    generation_type: str = "text_to_video"  # "text_to_video" | "image_to_video"
    original_prompt: str = ""
    final_prompt: str = ""
    negative_prompt: str = ""
    input_image_path: Optional[str] = None
    model: str = field(default_factory=lambda: settings.DEFAULT_VIDEO_MODEL)
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    duration_seconds: int = 8
    style: str = "cinematic"
    camera_motion: str = "tracking"
    status: TaskStatus = TaskStatus.PENDING
    status_message_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cancel_requested: bool = False


class InMemoryStateStore:
    """Manages personal user settings, pending drafts, and active tasks in RAM."""

    def __init__(self) -> None:
        self._preferences: dict[int, UserPreferences] = {}
        self._active_tasks: dict[str, VideoTaskItem] = {}
        self._draft_tasks: dict[int, VideoTaskItem] = {}

    def get_preferences(self, user_id: int) -> UserPreferences:
        if user_id not in self._preferences:
            self._preferences[user_id] = UserPreferences()
        return self._preferences[user_id]

    def set_draft(self, user_id: int, draft: VideoTaskItem) -> None:
        self._draft_tasks[user_id] = draft

    def get_draft(self, user_id: int) -> Optional[VideoTaskItem]:
        return self._draft_tasks.get(user_id)

    def pop_draft(self, user_id: int) -> Optional[VideoTaskItem]:
        return self._draft_tasks.pop(user_id, None)

    def register_task(self, task: VideoTaskItem) -> None:
        self._active_tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[VideoTaskItem]:
        return self._active_tasks.get(task_id)

    def remove_task(self, task_id: str) -> None:
        self._active_tasks.pop(task_id, None)

    def get_user_active_tasks(self, user_id: int) -> list[VideoTaskItem]:
        return [
            t
            for t in self._active_tasks.values()
            if t.user_id == user_id
            and t.status in (TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.DOWNLOADING)
        ]

    def request_cancel(self, task_id: str, user_id: int) -> bool:
        task = self._active_tasks.get(task_id)
        if not task or task.user_id != user_id:
            return False
        if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
            task.cancel_requested = True
            task.status = TaskStatus.CANCELLED
            return True
        return False


state_store = InMemoryStateStore()

