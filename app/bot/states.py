"""FSM States for Telegram AI Video Generator conversation flows."""

from aiogram.fsm.state import State, StatesGroup


class VideoGenStates(StatesGroup):
    """Conversation states for Text-to-Video, Image-to-Video, and Prompt Optimization."""

    waiting_for_text_prompt = State()
    waiting_for_image = State()
    waiting_for_image_prompt = State()
    waiting_for_optimize_only = State()
    confirming_generation = State()

