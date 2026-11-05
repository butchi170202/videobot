"""Asyncio background task runner for personal video generation without Redis/Celery."""

import asyncio
import html
import logging
from pathlib import Path
from aiogram import Bot
from aiogram.types import FSInputFile

from app.core.config import settings
from app.core.constants import MODEL_LABELS, TaskStatus
from app.core.state_store import VideoTaskItem, state_store
from app.services.gemini_service import (
    extract_video_thumbnail,
    gemini_video_service,
    get_video_dimensions,
)
from app.bot.keyboards import build_cancel_task_kb, build_main_menu_kb

logger = logging.getLogger(__name__)


class AsyncVideoTaskRunner:
    """Manages background video generation tasks with concurrency control and auto file cleanup."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)
        self._background_tasks: set[asyncio.Task] = set()

    def submit(self, bot: Bot, task: VideoTaskItem) -> None:
        """Schedule a video task to run asynchronously in the background."""
        state_store.register_task(task)
        bg_task = asyncio.create_task(self._execute_wrapper(bot, task))
        self._background_tasks.add(bg_task)
        bg_task.add_done_callback(self._background_tasks.discard)

    async def _execute_wrapper(self, bot: Bot, task: VideoTaskItem) -> None:
        output_video_path: Path | None = None
        thumb_path: Path | None = None
        try:
            async with self._semaphore:
                if task.cancel_requested:
                    await self._safe_edit_status(
                        bot,
                        task,
                        f"🛑 <b>Tác vụ #{task.task_id} đã được hủy.</b>",
                        reply_markup=None,
                    )
                    return

                task.status = TaskStatus.PROCESSING
                await self._safe_edit_status(
                    bot,
                    task,
                    (
                        f"🎬 <b>Đang dựng video (#{task.task_id})...</b>\n"
                        f"• <b>Model:</b> <code>{html.escape(MODEL_LABELS.get(task.model, task.model))}</code>\n"
                        f"• <b>Thông số:</b> <code>{task.aspect_ratio} | {task.resolution} | {task.duration_seconds}s</code>\n"
                        f"• <b>Trạng thái:</b> Đang gửi yêu cầu tới Google Veo...\n\n"
                        f"<i>Quá trình này thường mất từ 45 giây đến 2 phút. Bạn vẫn có thể dùng Bot bình thường.</i>"
                    ),
                    reply_markup=build_cancel_task_kb(task.task_id),
                )

                async def on_progress(elapsed_sec: int) -> None:
                    if task.cancel_requested:
                        return
                    await self._safe_edit_status(
                        bot,
                        task,
                        (
                            f"⏳ <b>AI đang kết xuất khung hình (#{task.task_id})...</b>\n"
                            f"• <b>Thời gian đã xử lý:</b> <code>{elapsed_sec} giây</code>\n"
                            f"• <b>Thông số:</b> <code>{task.aspect_ratio} | {task.resolution} | {task.duration_seconds}s</code>\n"
                            f"• <b>Prompt:</b> <i>{html.escape(task.final_prompt[:180])}...</i>"
                        ),
                        reply_markup=build_cancel_task_kb(task.task_id),
                    )

                # Retry up to 2 times on transient network errors
                max_attempts = 2
                for attempt in range(1, max_attempts + 1):
                    try:
                        output_video_path = await gemini_video_service.generate_video(
                            task=task,
                            progress_callback=on_progress,
                        )
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        if attempt < max_attempts and "timeout" in str(exc).lower():
                            logger.warning(
                                "Transient timeout on task %s (attempt %d/%d), retrying...",
                                task.task_id,
                                attempt,
                                max_attempts,
                            )
                            await asyncio.sleep(3)
                            continue
                        raise

                task.status = TaskStatus.DOWNLOADING
                await self._safe_edit_status(
                    bot,
                    task,
                    f"📥 <b>Đã tạo xong video (#{task.task_id})! Đang phát video trực tiếp lên Telegram...</b>",
                    reply_markup=None,
                )

                assert output_video_path is not None
                width, height = get_video_dimensions(task.aspect_ratio, task.resolution)
                thumb_path = await asyncio.to_thread(extract_video_thumbnail, output_video_path)

                caption = (
                    f"✅ <b>Video AI đã hoàn tất!</b>\n\n"
                    f"📝 <b>Prompt gốc:</b> {html.escape(task.original_prompt[:250])}\n"
                    f"⚙️ <b>Thông số:</b> <code>{task.aspect_ratio} ({width}x{height}) | {task.duration_seconds}s</code>\n"
                    f"🤖 <b>Model:</b> <code>{html.escape(task.model)}</code>"
                )
                if settings.GEMINI_MOCK_MODE:
                    caption += "\n\n🧪 <i>(Video mẫu phát trực tiếp ở chế độ GEMINI_MOCK_MODE=true)</i>"

                # Always send via send_video with width, height, duration, thumbnail, and supports_streaming=True
                # so Telegram plays it directly inline in chat!
                await bot.send_video(
                    chat_id=task.chat_id,
                    video=FSInputFile(str(output_video_path), filename=f"veo_{task.task_id}.mp4"),
                    duration=task.duration_seconds,
                    width=width,
                    height=height,
                    thumbnail=FSInputFile(str(thumb_path)) if thumb_path else None,
                    caption=caption,
                    parse_mode="HTML",
                    supports_streaming=True,
                )

                task.status = TaskStatus.COMPLETED
                await self._safe_delete_status(bot, task)
                await bot.send_message(
                    chat_id=task.chat_id,
                    text="🎉 Bạn muốn làm gì tiếp theo?",
                    reply_markup=build_main_menu_kb(),
                )

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            logger.info("Task %s cancelled by user %d", task.task_id, task.user_id)
            await self._safe_edit_status(
                bot,
                task,
                f"🛑 <b>Đã hủy tác vụ tạo video #{task.task_id}.</b>",
                reply_markup=build_main_menu_kb(),
            )
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            logger.error("Task %s failed: %s", task.task_id, exc)
            await self._safe_edit_status(
                bot,
                task,
                (
                    f"❌ <b>Tạo video thất bại (#{task.task_id})</b>\n\n"
                    f"<b>Lý do:</b> <code>{html.escape(str(exc)[:350])}</code>\n\n"
                    f"💡 <i>Hãy kiểm tra lại Prompt, API Key hoặc thử lại sau ít phút.</i>"
                ),
                reply_markup=build_main_menu_kb(),
            )
        finally:
            # Automatically clean up temporary input image, thumbnail, and output video files
            self._cleanup_file(output_video_path)
            self._cleanup_file(thumb_path)
            if task.input_image_path:
                self._cleanup_file(Path(task.input_image_path))
            state_store.remove_task(task.task_id)

    @staticmethod
    def _cleanup_file(file_path: Path | None) -> None:
        if file_path and file_path.exists():
            try:
                file_path.unlink(missing_ok=True)
                logger.debug("Cleaned up temporary file: %s", file_path.name)
            except Exception as exc:
                logger.warning("Failed to delete temp file %s: %s", file_path, exc)

    @staticmethod
    async def _safe_edit_status(
        bot: Bot,
        task: VideoTaskItem,
        text: str,
        reply_markup=None,
    ) -> None:
        if not task.status_message_id:
            return
        try:
            await bot.edit_message_text(
                chat_id=task.chat_id,
                message_id=task.status_message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        except Exception:
            pass

    @staticmethod
    async def _safe_delete_status(bot: Bot, task: VideoTaskItem) -> None:
        if not task.status_message_id:
            return
        try:
            await bot.delete_message(chat_id=task.chat_id, message_id=task.status_message_id)
        except Exception:
            pass


task_runner = AsyncVideoTaskRunner()
