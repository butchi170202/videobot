"""AI Prompt Optimization Service using Google Gemini 2.5 Flash."""

import logging
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.constants import (
    CAMERA_PROMPT_DESCRIPTIONS,
    DEFAULT_NEGATIVE_PROMPT,
    STYLE_PROMPT_DESCRIPTIONS,
)

logger = logging.getLogger(__name__)


class OptimizedPromptResult(BaseModel):
    """Structured output returned by Gemini Prompt Optimizer."""

    optimized_prompt: str = Field(
        description="Detailed English video generation prompt optimized for Google Veo 3.1"
    )
    negative_prompt: str = Field(
        description="Comma-separated list of visual defects and unwanted elements to avoid"
    )
    explanation_vi: str = Field(
        description="Short Vietnamese summary explaining how the prompt was enhanced"
    )


SYSTEM_INSTRUCTION = """You are an elite AI Video Prompt Director specializing in Google Veo 3.1 video generation.
Your task is to transform a user's raw idea (in Vietnamese or English) into a single, cohesive, ultra-detailed English prompt optimized for realistic, physically accurate video synthesis.

Your optimized prompt MUST explicitly weave together:
1. Subject: Clear, detailed description of the main subject(s), appearance, clothing, expressions.
2. Setting & Environment: Atmosphere, background elements, time of day, weather.
3. Action & Object Motion: Natural, fluid movement over 4-8 seconds.
4. Camera Movement & Framing: Shot size (close-up, wide, medium) and smooth camera trajectory.
5. Lighting & Color: Light sources, shadows, reflections, color palette.
6. Materials & Textures: Surface details (skin pores, fabric weave, water ripples, metallic reflections).
7. Physics & Frame Continuity: Realistic gravity, momentum, temporal consistency across frames.
8. Audio Cues (for Veo 3.1): Subtle ambient sound or sound effects matching the action.

Keep the optimized_prompt between 70 and 150 words in English.
Also provide a tailored negative_prompt to prevent distortion, morphing, or illogical physics, and a short Vietnamese note (explanation_vi) summarizing the enhancements."""


class PromptService:
    """Service that optimizes raw user prompts for Veo video generation."""

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            if settings.USE_VERTEX_AI:
                self._client = genai.Client(
                    vertexai=True,
                    project=settings.VERTEX_PROJECT_ID,
                    location=settings.VERTEX_LOCATION,
                )
            else:
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    def build_styled_prompt(
        self,
        base_prompt: str,
        style_key: str,
        camera_key: str,
    ) -> str:
        """Append selected visual style and camera motion cues to a prompt."""
        style_desc = STYLE_PROMPT_DESCRIPTIONS.get(style_key, STYLE_PROMPT_DESCRIPTIONS["cinematic"])
        camera_desc = CAMERA_PROMPT_DESCRIPTIONS.get(camera_key, CAMERA_PROMPT_DESCRIPTIONS["tracking"])
        return f"{base_prompt.strip()}. Camera: {camera_desc}. Style: {style_desc}."

    async def optimize_prompt(
        self,
        raw_prompt: str,
        style_key: str = "cinematic",
        camera_key: str = "tracking",
        is_image_to_video: bool = False,
    ) -> OptimizedPromptResult:
        """Use Gemini 2.5 Flash to optimize a user prompt into a cinematic Veo prompt."""
        style_desc = STYLE_PROMPT_DESCRIPTIONS.get(style_key, STYLE_PROMPT_DESCRIPTIONS["cinematic"])
        camera_desc = CAMERA_PROMPT_DESCRIPTIONS.get(camera_key, CAMERA_PROMPT_DESCRIPTIONS["tracking"])

        if settings.GEMINI_MOCK_MODE:
            enhanced = (
                f"Cinematic shot based on '{raw_prompt.strip()}', featuring natural fluid motion, "
                f"physically accurate dynamics, rich surface textures, and temporal frame consistency. "
                f"Camera movement: {camera_desc}. Visual style: {style_desc}, subtle ambient audio."
            )
            return OptimizedPromptResult(
                optimized_prompt=enhanced,
                negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                explanation_vi="[Chế độ Mock] Đã tự động bổ sung mô tả chuyển động vật lý, ánh sáng, góc máy và phong cách hình ảnh.",
            )

        mode_hint = (
            "This prompt is for Image-to-Video: focus heavily on how the existing scene and subject in the reference image should animate and move naturally."
            if is_image_to_video
            else "This prompt is for Text-to-Video: describe the full scene, subject, and motion from scratch."
        )

        user_request = (
            f"User input: {raw_prompt}\n"
            f"Requested Visual Style: {style_desc}\n"
            f"Requested Camera Movement: {camera_desc}\n"
            f"Mode: {mode_hint}"
        )

        try:
            client = self._get_client()
            response = await client.aio.models.generate_content(
                model=settings.PROMPT_OPTIMIZER_MODEL,
                contents=user_request,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=OptimizedPromptResult,
                ),
            )
            if response.parsed and isinstance(response.parsed, OptimizedPromptResult):
                return response.parsed

            # Fallback if JSON parsing didn't populate .parsed
            text_out = (response.text or "").strip()
            if text_out:
                return OptimizedPromptResult.model_validate_json(text_out)
        except Exception as exc:
            logger.warning("Prompt optimization via Gemini failed, falling back to template: %s", exc)

        fallback_prompt = self.build_styled_prompt(raw_prompt, style_key, camera_key)
        return OptimizedPromptResult(
            optimized_prompt=fallback_prompt,
            negative_prompt=DEFAULT_NEGATIVE_PROMPT,
            explanation_vi="Đã ghép nối tự động phong cách hình ảnh và chuyển động camera vào prompt gốc.",
        )


prompt_service = PromptService()

