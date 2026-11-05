"""Unit tests for Personal Telegram AI Video Generator services and state store."""

import asyncio
import logging
import pytest

from app.core.config import settings
from app.core.constants import TaskStatus
from app.core.logging import SecretMaskingFilter
from app.core.state_store import InMemoryStateStore, UserPreferences, VideoTaskItem
from app.services.gemini_service import gemini_video_service
from app.services.prompt_service import prompt_service


def test_user_preferences_1080p_enforces_8s_duration() -> None:
    """Verify Veo 3.1 constraint: 1080p resolution automatically adjusts duration to 8s."""
    prefs = UserPreferences(resolution="1080p", duration_seconds=4)
    note = prefs.ensure_valid_combination()
    assert prefs.duration_seconds == 8
    assert note is not None and "8 giây" in note


def test_in_memory_state_store_lifecycle() -> None:
    """Test draft storage, active task registration, and cancellation."""
    store = InMemoryStateStore()
    user_id = 999888777

    draft = VideoTaskItem(user_id=user_id, chat_id=user_id, original_prompt="A cat flying")
    store.set_draft(user_id, draft)
    assert store.get_draft(user_id) is draft

    popped = store.pop_draft(user_id)
    assert popped is draft
    assert store.get_draft(user_id) is None

    store.register_task(draft)
    assert len(store.get_user_active_tasks(user_id)) == 1

    cancelled = store.request_cancel(draft.task_id, user_id)
    assert cancelled is True
    assert draft.status == TaskStatus.CANCELLED
    assert len(store.get_user_active_tasks(user_id)) == 0


def test_secret_masking_filter() -> None:
    """Ensure API Keys and Bot Tokens are never leaked into logs."""
    filt = SecretMaskingFilter()
    fake_msg = "Error with token 1234567890:AAH_test_secret_token_value_1234567 and key AIzaSyD-1234567890abcdefghijklmnopqrstuv"
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=1,
        msg=fake_msg,
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert "AIzaSyD" not in record.getMessage()
    assert "AAH_test_secret" not in record.getMessage()
    assert "***REDACTED_SECRET***" in record.getMessage()


@pytest.mark.asyncio
async def test_prompt_optimization_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify prompt optimizer works in mock mode without calling external API."""
    monkeypatch.setattr(settings, "GEMINI_MOCK_MODE", True)
    res = await prompt_service.optimize_prompt(
        raw_prompt="Một chiếc siêu xe chạy dưới mưa đêm Tokyo",
        style_key="cinematic",
        camera_key="tracking",
    )
    assert "Một chiếc siêu xe" in res.optimized_prompt
    assert "tracking" in res.optimized_prompt.lower()
    assert len(res.negative_prompt) > 10


@pytest.mark.asyncio
async def test_gemini_video_service_mock_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify mock video generation creates a real playable H.264 MP4 file and cleans up."""
    monkeypatch.setattr(settings, "GEMINI_MOCK_MODE", True)
    task = VideoTaskItem(
        user_id=123,
        chat_id=123,
        original_prompt="Sunset over ocean",
        final_prompt="Cinematic sunset over ocean waves",
        duration_seconds=4,
    )
    output_path = await gemini_video_service.generate_video(task)
    try:
        assert output_path.exists()
        assert output_path.stat().st_size > 10000
    finally:
        output_path.unlink(missing_ok=True)

