"""Google Gemini / Veo Video Generation Service using official google-genai SDK."""

import asyncio
import logging
import mimetypes
from pathlib import Path
import subprocess
from typing import Awaitable, Callable, Optional

from google import genai
from google.genai import types
import imageio_ffmpeg

from app.core.config import TEMP_STORAGE_DIR, settings
from app.core.constants import DEFAULT_NEGATIVE_PROMPT
from app.core.state_store import VideoTaskItem

logger = logging.getLogger(__name__)


def get_video_dimensions(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    """Return (width, height) in pixels based on aspect ratio and resolution."""
    is_1080p = resolution == "1080p"
    if aspect_ratio == "9:16":
        return (1080, 1920) if is_1080p else (720, 1280)
    return (1920, 1080) if is_1080p else (1280, 720)


def _generate_playable_mock_mp4(task: VideoTaskItem, output_path: Path) -> None:
    """
    Generate a real, playable H.264 (yuv420p + faststart) MP4 video using bundled ffmpeg
    so Telegram displays and plays the video inline in chat during Mock Mode testing.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    width, height = get_video_dimensions(task.aspect_ratio, task.resolution)
    duration = max(2, min(8, task.duration_seconds))

    # If user uploaded an image in Image-to-Video mode, animate that image with smooth zoom
    if task.generation_type == "image_to_video" and task.input_image_path and Path(task.input_image_path).exists():
        vf_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},format=yuv420p"
        )
        cmd = [
            ffmpeg_exe,
            "-y",
            "-loop",
            "1",
            "-i",
            str(task.input_image_path),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            str(duration),
            "-vf",
            vf_filter,
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    else:
        # Generate a colorful animated test pattern MP4 with ambient sine wave audio
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={width}x{height}:rate=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=432:sample_rate=44100",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0 or not output_path.exists():
        logger.error("FFmpeg mock video generation failed: %s", res.stderr)
        raise RuntimeError("Không thể tạo video MP4 mẫu bằng FFmpeg.")


def extract_video_thumbnail(video_path: Path) -> Optional[Path]:
    """Extract the first frame of an MP4 video as a JPEG thumbnail for Telegram inline player."""
    thumb_path = video_path.with_suffix(".jpg")
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            "-y",
            "-ss",
            "00:00:00.500",
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-vf",
            "scale='min(320,iw)':-1",
            "-q:v",
            "4",
            str(thumb_path),
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        if thumb_path.exists() and thumb_path.stat().st_size > 0:
            return thumb_path
    except Exception as exc:
        logger.debug("Could not extract thumbnail: %s", exc)
    return None


class GeminiVideoService:
    """Wrapper around official google-genai SDK for Veo Text-to-Video and Image-to-Video."""

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
                if not settings.GEMINI_API_KEY:
                    raise RuntimeError(
                        "Chưa cấu hình GEMINI_API_KEY trong file .env (hoặc bật GEMINI_MOCK_MODE=true để test)."
                    )
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    @staticmethod
    def _load_image_input(image_path: str) -> types.Image:
        """Load and validate a local image into google.genai.types.Image."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file ảnh đầu vào: {image_path}")

        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type not in ("image/jpeg", "image/png", "image/webp"):
            mime_type = "image/jpeg"

        image_bytes = path.read_bytes()
        return types.Image(image_bytes=image_bytes, mime_type=mime_type)

    async def generate_video(
        self,
        task: VideoTaskItem,
        progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
    ) -> Path:
        """
        Submit video generation job to Google Veo API, poll until completion,
        download the resulting MP4 file into TEMP_STORAGE_DIR, and return its Path.
        """
        output_path = TEMP_STORAGE_DIR / f"video_{task.task_id}.mp4"

        # 1. Handle Mock Mode for zero-cost testing (generates a real H.264 playable MP4)
        if settings.GEMINI_MOCK_MODE:
            logger.info("[MOCK MODE] Generating playable H.264 MP4 for task %s", task.task_id)
            for elapsed in (2, 4):
                if task.cancel_requested:
                    raise asyncio.CancelledError("Tác vụ đã bị hủy bởi người dùng.")
                await asyncio.sleep(2)
                if progress_callback:
                    await progress_callback(elapsed)
            await asyncio.to_thread(_generate_playable_mock_mp4, task, output_path)
            return output_path

        # 2. Real Google Veo API Call
        client = self._get_client()

        config_kwargs: dict = {
            "aspect_ratio": task.aspect_ratio,
            "negative_prompt": task.negative_prompt or DEFAULT_NEGATIVE_PROMPT,
        }

        if "veo-3" in task.model:
            config_kwargs["resolution"] = task.resolution
            config_kwargs["duration_seconds"] = task.duration_seconds
        else:
            config_kwargs["duration_seconds"] = max(5, min(8, task.duration_seconds))

        video_config = types.GenerateVideosConfig(**config_kwargs)

        image_obj: Optional[types.Image] = None
        if task.generation_type == "image_to_video" and task.input_image_path:
            image_obj = await asyncio.to_thread(self._load_image_input, task.input_image_path)

        logger.info(
            "Submitting Veo job | task=%s | model=%s | type=%s | ratio=%s | res=%s | dur=%ss",
            task.task_id,
            task.model,
            task.generation_type,
            task.aspect_ratio,
            task.resolution,
            task.duration_seconds,
        )

        def _start_operation():
            if image_obj is not None:
                return client.models.generate_videos(
                    model=task.model,
                    prompt=task.final_prompt,
                    image=image_obj,
                    config=video_config,
                )
            return client.models.generate_videos(
                model=task.model,
                prompt=task.final_prompt,
                config=video_config,
            )

        operation = await asyncio.to_thread(_start_operation)

        # 3. Poll Long-Running Operation (LRO)
        elapsed_seconds = 0
        poll_interval = settings.POLL_INTERVAL_SECONDS
        max_wait = settings.MAX_WAIT_SECONDS

        while not operation.done:
            if task.cancel_requested:
                raise asyncio.CancelledError("Tác vụ đã bị hủy bởi người dùng.")

            await asyncio.sleep(poll_interval)
            elapsed_seconds += poll_interval

            if elapsed_seconds > max_wait:
                raise TimeoutError(
                    f"Quá thời gian chờ ({max_wait}s) khi tạo video từ Google Veo API."
                )

            operation = await asyncio.to_thread(client.operations.get, operation)

            if progress_callback:
                await progress_callback(elapsed_seconds)

        # 4. Validate response and download MP4
        if getattr(operation, "error", None):
            raise RuntimeError(f"Google Veo API trả về lỗi: {operation.error}")

        response = getattr(operation, "response", None)
        generated_videos = getattr(response, "generated_videos", None) if response else None
        if not generated_videos:
            raise RuntimeError(
                "API hoàn tất nhưng không trả về video (có thể nội dung bị chặn bởi bộ lọc an toàn của Google)."
            )

        generated_video = generated_videos[0]

        def _download_and_save() -> None:
            client.files.download(file=generated_video.video)
            generated_video.video.save(str(output_path))

        await asyncio.to_thread(_download_and_save)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Không thể lưu file video tải về từ Google Gemini API.")

        logger.info(
            "Video downloaded successfully | task=%s | path=%s | size=%d bytes",
            task.task_id,
            output_path.name,
            output_path.stat().st_size,
        )
        return output_path


gemini_video_service = GeminiVideoService()
