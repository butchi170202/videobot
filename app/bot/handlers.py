"""All Telegram Bot command and callback handlers for Personal AI Video Generator."""

import html
import logging
import uuid
from PIL import Image
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    build_back_to_menu_kb,
    build_cancel_task_kb,
    build_confirm_generation_kb,
    build_main_menu_kb,
    build_settings_overview_kb,
    build_sub_setting_kb,
)
from app.bot.states import VideoGenStates
from app.core.config import TEMP_STORAGE_DIR, settings
from app.core.constants import (
    CAMERA_MOTIONS,
    DEFAULT_NEGATIVE_PROMPT,
    MODEL_LABELS,
    SUPPORTED_ASPECT_RATIOS,
    SUPPORTED_DURATIONS,
    SUPPORTED_RESOLUTIONS,
    VIDEO_STYLES,
)
from app.core.state_store import UserPreferences, VideoTaskItem, state_store
from app.services.prompt_service import prompt_service
from app.services.task_runner import task_runner

logger = logging.getLogger(__name__)
router = Router(name="personal_video_bot")


def _format_settings_summary(prefs: UserPreferences) -> str:
    mode_tag = "🧪 Đang bật MOCK MODE (Test miễn phí)" if settings.GEMINI_MOCK_MODE else "🟢 Kết nối Google Veo API thật"
    opt_text = "Tự động tối ưu bằng Gemini AI" if prefs.auto_optimize_prompt else "Chỉ ghép nối phong cách cơ bản"
    return (
        f"⚙️ <b>CÀI ĐẶT VIDEO HIỆN TẠI CỦA BẠN</b>\n\n"
        f"• <b>Chế độ hệ thống:</b> <code>{mode_tag}</code>\n"
        f"• <b>Model tạo video:</b> <code>{html.escape(MODEL_LABELS.get(prefs.model, prefs.model))}</code>\n"
        f"• <b>Tỷ lệ khung hình:</b> <code>{prefs.aspect_ratio}</code>\n"
        f"• <b>Độ phân giải:</b> <code>{prefs.resolution}</code>\n"
        f"• <b>Thời lượng:</b> <code>{prefs.duration_seconds} giây</code>\n"
        f"• <b>Phong cách:</b> <code>{html.escape(VIDEO_STYLES.get(prefs.style, prefs.style))}</code>\n"
        f"• <b>Chuyển động Camera:</b> <code>{html.escape(CAMERA_MOTIONS.get(prefs.camera_motion, prefs.camera_motion))}</code>\n"
        f"• <b>Chất lượng Prompt:</b> <code>{opt_text}</code>"
    )


def _format_draft_preview(draft: VideoTaskItem, is_optimized: bool, note_vi: str = "") -> str:
    gen_label = "🖼️ Tạo Video từ Hình ảnh" if draft.generation_type == "image_to_video" else "🎬 Tạo Video từ Văn bản"
    note_block = f"\n💡 <b>Ghi chú AI:</b> <i>{html.escape(note_vi)}</i>\n" if note_vi else ""
    return (
        f"🔍 <b>XÁC NHẬN THÔNG SỐ TRƯỚC KHI TẠO VIDEO</b>\n\n"
        f"• <b>Chế độ:</b> {gen_label}\n"
        f"• <b>Model:</b> <code>{html.escape(MODEL_LABELS.get(draft.model, draft.model))}</code>\n"
        f"• <b>Cấu hình:</b> <code>{draft.aspect_ratio} | {draft.resolution} | {draft.duration_seconds}s</code>\n"
        f"• <b>Phong cách & Camera:</b> <code>{draft.style} / {draft.camera_motion}</code>\n\n"
        f"📝 <b>Prompt gốc:</b>\n<i>{html.escape(draft.original_prompt)}</i>\n\n"
        f"✨ <b>Prompt gửi tới Veo ({'Đã tối ưu AI' if is_optimized else 'Cơ bản'}):</b>\n"
        f"<code>{html.escape(draft.final_prompt)}</code>"
        f"{note_block}\n"
        f"Bạn hãy bấm <b>🚀 Xác nhận tạo Video ngay</b> để bắt đầu!"
    )


# ==============================================================================
# 1. START, HELP & MAIN MENU
# ==============================================================================


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id if message.from_user else 0
    prefs = state_store.get_preferences(user_id)
    welcome_text = (
        f"👋 <b>Xin chào {html.escape(message.from_user.full_name if message.from_user else 'bạn')}!</b>\n"
        f"🆔 <b>Telegram ID của bạn:</b> <code>{user_id}</code>\n"
        f"Chào mừng bạn đến với <b>Personal Telegram AI Video Generator</b> (Google Veo 3.1).\n\n"
        f"{_format_settings_summary(prefs)}\n\n"
        f"👇 <b>Hãy chọn chức năng bên dưới (hoặc gõ trực tiếp mô tả video vào khung chat):</b>"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=build_main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(_get_help_text(), parse_mode="HTML", reply_markup=build_main_menu_kb())


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    prefs = state_store.get_preferences(user_id)
    await message.answer(
        _format_settings_summary(prefs),
        parse_mode="HTML",
        reply_markup=build_settings_overview_kb(prefs),
    )


def _get_help_text() -> str:
    return (
        "📖 <b>HƯỚNG DẪN SỬ DỤNG BOT TẠO VIDEO CÁ NHÂN</b>\n\n"
        "1️⃣ <b>Tạo video từ văn bản (Text-to-Video):</b>\n"
        "   • Bấm nút <b>🎬 Tạo video từ văn bản</b> (hoặc nhắn trực tiếp ý tưởng vào chat).\n"
        "   • Bạn có thể viết bằng tiếng Việt ngắn gọn, AI sẽ tự động dịch và tối ưu sang chuẩn điện ảnh tiếng Anh cho Google Veo 3.1.\n\n"
        "2️⃣ <b>Tạo video từ hình ảnh (Image-to-Video):</b>\n"
        "   • Bấm nút <b>🖼️ Tạo video từ hình ảnh</b> (hoặc gửi trực tiếp 1 bức ảnh kèm chú thích).\n"
        "   • Mô tả cách bạn muốn bức ảnh chuyển động.\n\n"
        "3️⃣ <b>Tùy chỉnh thông số (⚙️ Cài đặt):</b>\n"
        "   • Hỗ trợ tỷ lệ <code>16:9</code> (Ngang) và <code>9:16</code> (Dọc TikTok/Reels).\n"
        "   • Độ phân giải <code>720p</code> hoặc <code>1080p</code> (lưu ý: 1080p trên Veo 3.1 yêu cầu thời lượng 8 giây).\n"
        "   • Thời lượng <code>4s</code>, <code>6s</code>, <code>8s</code>.\n\n"
        "4️⃣ <b>Quản lý file tự động:</b>\n"
        "   • Ngay sau khi Bot gửi file MP4 về Telegram cho bạn, file tạm trên máy chủ sẽ tự động được xóa sạch để không tốn dung lượng ổ cứng."
    )


@router.callback_query(F.data == "menu:home")
async def cb_menu_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = callback.from_user.id
    # Clean up any unused draft image if user cancels before confirming
    draft = state_store.pop_draft(user_id)
    if draft and draft.input_image_path:
        task_runner._cleanup_file(TEMP_STORAGE_DIR / draft.input_image_path)

    prefs = state_store.get_preferences(user_id)
    text = f"🏠 <b>MENU CHÍNH</b>\n\n{_format_settings_summary(prefs)}"
    if callback.message:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=build_main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def cb_menu_help(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            _get_help_text(),
            parse_mode="HTML",
            reply_markup=build_back_to_menu_kb(),
        )
    await callback.answer()


# ==============================================================================
# 2. VIDEO SETTINGS CONFIGURATION
# ==============================================================================


@router.callback_query(F.data == "menu:settings")
async def cb_menu_settings(callback: CallbackQuery) -> None:
    prefs = state_store.get_preferences(callback.from_user.id)
    if callback.message:
        await callback.message.edit_text(
            _format_settings_summary(prefs),
            parse_mode="HTML",
            reply_markup=build_settings_overview_kb(prefs),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("set_menu:"))
async def cb_open_sub_setting(callback: CallbackQuery) -> None:
    category = (callback.data or "").split(":", 1)[1]
    prefs = state_store.get_preferences(callback.from_user.id)

    current_map = {
        "aspect_ratio": prefs.aspect_ratio,
        "resolution": prefs.resolution,
        "duration": prefs.duration_seconds,
        "style": prefs.style,
        "camera": prefs.camera_motion,
        "model": prefs.model,
    }
    title_map = {
        "aspect_ratio": "📐 Chọn tỷ lệ khung hình (Veo hỗ trợ 16:9 và 9:16):",
        "resolution": "🎞️ Chọn độ phân giải video:",
        "duration": "⏱️ Chọn thời lượng video (giây):",
        "style": "🎨 Chọn phong cách hình ảnh:",
        "camera": "🎥 Chọn chuyển động Camera:",
        "model": "🤖 Chọn Model Google Veo:",
    }

    if callback.message and category in current_map:
        await callback.message.edit_text(
            f"<b>{title_map[category]}</b>",
            parse_mode="HTML",
            reply_markup=build_sub_setting_kb(category, current_map[category]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("set_val:"))
async def cb_update_setting_value(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":", 2)
    prefs = state_store.get_preferences(callback.from_user.id)
    adjustment_note = None

    if parts[1] == "toggle_optimize":
        prefs.auto_optimize_prompt = not prefs.auto_optimize_prompt
    elif len(parts) == 3:
        category, val = parts[1], parts[2]
        if category == "aspect_ratio" and val in SUPPORTED_ASPECT_RATIOS:
            prefs.aspect_ratio = val
        elif category == "resolution" and val in SUPPORTED_RESOLUTIONS:
            prefs.resolution = val
            adjustment_note = prefs.ensure_valid_combination()
        elif category == "duration" and val.isdigit() and int(val) in SUPPORTED_DURATIONS:
            prefs.duration_seconds = int(val)
            adjustment_note = prefs.ensure_valid_combination()
        elif category == "style" and val in VIDEO_STYLES:
            prefs.style = val
        elif category == "camera" and val in CAMERA_MOTIONS:
            prefs.camera_motion = val
        elif category == "model" and val in MODEL_LABELS:
            prefs.model = val

    # Also sync changes to any existing unconfirmed draft task
    draft = state_store.get_draft(callback.from_user.id)
    if draft:
        draft.model = prefs.model
        draft.aspect_ratio = prefs.aspect_ratio
        draft.resolution = prefs.resolution
        draft.duration_seconds = prefs.duration_seconds
        draft.style = prefs.style
        draft.camera_motion = prefs.camera_motion

    if callback.message:
        summary = _format_settings_summary(prefs)
        if adjustment_note:
            summary += f"\n\n⚠️ <i>{html.escape(adjustment_note)}</i>"
        await callback.message.edit_text(
            summary,
            parse_mode="HTML",
            reply_markup=build_settings_overview_kb(prefs),
        )
    await callback.answer(adjustment_note or "✅ Đã lưu cài đặt!", show_alert=bool(adjustment_note))


# ==============================================================================
# 3. TEXT-TO-VIDEO FLOW
# ==============================================================================


@router.callback_query(F.data == "menu:text_to_video")
async def cb_start_text_to_video(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(VideoGenStates.waiting_for_text_prompt)
    if callback.message:
        await callback.message.edit_text(
            "🎬 <b>TẠO VIDEO TỪ VĂN BẢN (TEXT-TO-VIDEO)</b>\n\n"
            "Hãy nhập mô tả cảnh quay bạn muốn tạo (bằng tiếng Việt hoặc tiếng Anh).\n"
            "<i>Ví dụ: Một chú chó Golden đang chạy trên cánh đồng hoa hướng dương lúc hoàng hôn, ánh nắng ấm áp.</i>",
            parse_mode="HTML",
            reply_markup=build_back_to_menu_kb(),
        )
    await callback.answer()


@router.message(VideoGenStates.waiting_for_text_prompt, F.text)
async def handle_text_prompt_input(message: Message, state: FSMContext) -> None:
    await _prepare_text_video_draft(message, state)


async def _prepare_text_video_draft(message: Message, state: FSMContext) -> None:
    raw_prompt = (message.text or "").strip()
    if len(raw_prompt) < 3:
        await message.answer("⚠️ Mô tả quá ngắn. Vui lòng nhập ít nhất 3 ký tự.")
        return
    if len(raw_prompt) > 2000:
        await message.answer("⚠️ Mô tả quá dài (tối đa 2000 ký tự).")
        return

    user_id = message.from_user.id if message.from_user else 0
    prefs = state_store.get_preferences(user_id)
    prefs.ensure_valid_combination()

    wait_msg = await message.answer("⏳ <i>Đang chuẩn bị thông số và xử lý Prompt...</i>", parse_mode="HTML")

    note_vi = ""
    is_optimized = False
    if prefs.auto_optimize_prompt:
        opt_res = await prompt_service.optimize_prompt(
            raw_prompt=raw_prompt,
            style_key=prefs.style,
            camera_key=prefs.camera_motion,
            is_image_to_video=False,
        )
        final_prompt = opt_res.optimized_prompt
        neg_prompt = opt_res.negative_prompt
        note_vi = opt_res.explanation_vi
        is_optimized = True
    else:
        final_prompt = prompt_service.build_styled_prompt(
            base_prompt=raw_prompt,
            style_key=prefs.style,
            camera_key=prefs.camera_motion,
        )
        neg_prompt = DEFAULT_NEGATIVE_PROMPT

    draft = VideoTaskItem(
        user_id=user_id,
        chat_id=message.chat.id,
        generation_type="text_to_video",
        original_prompt=raw_prompt,
        final_prompt=final_prompt,
        negative_prompt=neg_prompt,
        model=prefs.model,
        aspect_ratio=prefs.aspect_ratio,
        resolution=prefs.resolution,
        duration_seconds=prefs.duration_seconds,
        style=prefs.style,
        camera_motion=prefs.camera_motion,
    )
    state_store.set_draft(user_id, draft)
    await state.set_state(VideoGenStates.confirming_generation)

    await wait_msg.edit_text(
        _format_draft_preview(draft, is_optimized=is_optimized, note_vi=note_vi),
        parse_mode="HTML",
        reply_markup=build_confirm_generation_kb(is_optimized=is_optimized),
    )


# ==============================================================================
# 4. IMAGE-TO-VIDEO FLOW
# ==============================================================================


@router.callback_query(F.data == "menu:image_to_video")
async def cb_start_image_to_video(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(VideoGenStates.waiting_for_image)
    if callback.message:
        await callback.message.edit_text(
            "🖼️ <b>TẠO VIDEO TỪ HÌNH ẢNH (IMAGE-TO-VIDEO)</b>\n\n"
            "Hãy gửi <b>1 bức ảnh</b> (Photo hoặc File ảnh JPG/PNG, tối đa 10 MB).\n"
            "💡 <i>Bạn có thể nhập luôn mô tả chuyển động vào phần Chú thích (Caption) của ảnh, hoặc gửi ảnh trước rồi nhập mô tả sau.</i>",
            parse_mode="HTML",
            reply_markup=build_back_to_menu_kb(),
        )
    await callback.answer()


@router.message(VideoGenStates.waiting_for_image, F.photo | F.document)
@router.message(F.photo)
async def handle_image_upload(message: Message, state: FSMContext, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0

    # Extract file_id and file_size from Photo or Document
    file_id: str | None = None
    file_size: int = 0
    ext = ".jpg"

    if message.photo:
        largest_photo = message.photo[-1]
        file_id = largest_photo.file_id
        file_size = largest_photo.file_size or 0
    elif message.document:
        mime = (message.document.mime_type or "").lower()
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            await message.answer("⚠️ Chỉ hỗ trợ file ảnh định dạng JPEG, PNG hoặc WEBP.")
            return
        file_id = message.document.file_id
        file_size = message.document.file_size or 0
        if mime == "image/png":
            ext = ".png"
        elif mime == "image/webp":
            ext = ".webp"

    if not file_id:
        await message.answer("⚠️ Không tìm thấy ảnh hợp lệ.")
        return

    max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        await message.answer(
            f"⚠️ Dung lượng ảnh vượt quá giới hạn cho phép ({settings.MAX_IMAGE_SIZE_MB} MB)."
        )
        return

    status_msg = await message.answer("📥 <i>Đang tải và kiểm tra chất lượng ảnh...</i>", parse_mode="HTML")
    image_filename = f"input_{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    image_path = TEMP_STORAGE_DIR / image_filename

    try:
        tg_file = await bot.get_file(file_id)
        if not tg_file.file_path:
            raise RuntimeError("Không lấy được đường dẫn file từ Telegram.")
        await bot.download_file(tg_file.file_path, destination=image_path)

        # Verify image integrity & dimensions using Pillow
        with Image.open(image_path) as img:
            img.verify()
        with Image.open(image_path) as img2:
            width, height = img2.size
            if width < 256 or height < 256:
                image_path.unlink(missing_ok=True)
                await status_msg.edit_text(
                    f"⚠️ Độ phân giải ảnh quá thấp ({width}x{height}). Vui lòng gửi ảnh tối thiểu 256x256 pixel."
                )
                return
    except Exception as exc:
        image_path.unlink(missing_ok=True)
        logger.error("Image validation failed: %s", exc)
        await status_msg.edit_text("❌ File ảnh bị lỗi hoặc không hợp lệ. Vui lòng thử ảnh khác.")
        return

    await state.update_data(input_image_path=str(image_path))

    # If user already provided a caption with the image, proceed directly to draft confirmation
    caption = (message.caption or "").strip()
    if len(caption) >= 3:
        await status_msg.delete()
        await _prepare_image_video_draft(message, state, str(image_path), caption)
        return

    await state.set_state(VideoGenStates.waiting_for_image_prompt)
    await status_msg.edit_text(
        f"✅ <b>Đã nhận ảnh thành công ({width}x{height} px)!</b>\n\n"
        "Bây giờ, hãy nhập <b>mô tả chuyển động</b> bạn muốn AI thực hiện cho bức ảnh này:\n"
        "<i>Ví dụ: Máy quay đẩy nhẹ vào chủ thể, gió thổi tóc bay nhẹ, ánh sáng lung linh.</i>",
        parse_mode="HTML",
        reply_markup=build_back_to_menu_kb(),
    )


@router.message(VideoGenStates.waiting_for_image_prompt, F.text)
async def handle_image_motion_prompt(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    image_path = data.get("input_image_path")
    if not image_path:
        await state.clear()
        await message.answer("⚠️ Phiên gửi ảnh đã hết hạn. Vui lòng gửi lại ảnh.", reply_markup=build_main_menu_kb())
        return

    motion_prompt = (message.text or "").strip()
    if len(motion_prompt) < 3:
        await message.answer("⚠️ Vui lòng nhập mô tả chuyển động ít nhất 3 ký tự.")
        return

    await _prepare_image_video_draft(message, state, image_path, motion_prompt)


async def _prepare_image_video_draft(
    message: Message,
    state: FSMContext,
    image_path: str,
    motion_prompt: str,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    prefs = state_store.get_preferences(user_id)
    prefs.ensure_valid_combination()

    wait_msg = await message.answer("⏳ <i>Đang tối ưu kịch bản chuyển động cho ảnh...</i>", parse_mode="HTML")

    note_vi = ""
    is_optimized = False
    if prefs.auto_optimize_prompt:
        opt_res = await prompt_service.optimize_prompt(
            raw_prompt=motion_prompt,
            style_key=prefs.style,
            camera_key=prefs.camera_motion,
            is_image_to_video=True,
        )
        final_prompt = opt_res.optimized_prompt
        neg_prompt = opt_res.negative_prompt
        note_vi = opt_res.explanation_vi
        is_optimized = True
    else:
        final_prompt = prompt_service.build_styled_prompt(
            base_prompt=motion_prompt,
            style_key=prefs.style,
            camera_key=prefs.camera_motion,
        )
        neg_prompt = DEFAULT_NEGATIVE_PROMPT

    draft = VideoTaskItem(
        user_id=user_id,
        chat_id=message.chat.id,
        generation_type="image_to_video",
        original_prompt=motion_prompt,
        final_prompt=final_prompt,
        negative_prompt=neg_prompt,
        input_image_path=image_path,
        model=prefs.model,
        aspect_ratio=prefs.aspect_ratio,
        resolution=prefs.resolution,
        duration_seconds=prefs.duration_seconds,
        style=prefs.style,
        camera_motion=prefs.camera_motion,
    )
    state_store.set_draft(user_id, draft)
    await state.set_state(VideoGenStates.confirming_generation)

    await wait_msg.edit_text(
        _format_draft_preview(draft, is_optimized=is_optimized, note_vi=note_vi),
        parse_mode="HTML",
        reply_markup=build_confirm_generation_kb(is_optimized=is_optimized),
    )


# ==============================================================================
# 5. STANDALONE AI PROMPT OPTIMIZER
# ==============================================================================


@router.callback_query(F.data == "menu:optimize_prompt")
async def cb_start_optimize_only(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(VideoGenStates.waiting_for_optimize_only)
    if callback.message:
        await callback.message.edit_text(
            "✍️ <b>TỐI ƯU PROMPT CHUYÊN NGHIỆP BẰNG GEMINI AI</b>\n\n"
            "Hãy gửi ý tưởng ngắn gọn của bạn. AI sẽ viết lại thành bản Prompt tiếng Anh chuẩn điện ảnh (đầy đủ chủ thể, bối cảnh, ánh sáng, vật lý, góc máy) và cho phép bạn tạo video ngay nếu ưng ý!",
            parse_mode="HTML",
            reply_markup=build_back_to_menu_kb(),
        )
    await callback.answer()


@router.message(VideoGenStates.waiting_for_optimize_only, F.text)
async def handle_optimize_only_input(message: Message, state: FSMContext) -> None:
    raw_prompt = (message.text or "").strip()
    if len(raw_prompt) < 3:
        await message.answer("⚠️ Vui lòng nhập ý tưởng ít nhất 3 ký tự.")
        return

    user_id = message.from_user.id if message.from_user else 0
    prefs = state_store.get_preferences(user_id)
    prefs.ensure_valid_combination()

    wait_msg = await message.answer("✨ <i>Gemini AI đang phân tích và viết lại Prompt điện ảnh...</i>", parse_mode="HTML")
    opt_res = await prompt_service.optimize_prompt(
        raw_prompt=raw_prompt,
        style_key=prefs.style,
        camera_key=prefs.camera_motion,
        is_image_to_video=False,
    )

    draft = VideoTaskItem(
        user_id=user_id,
        chat_id=message.chat.id,
        generation_type="text_to_video",
        original_prompt=raw_prompt,
        final_prompt=opt_res.optimized_prompt,
        negative_prompt=opt_res.negative_prompt,
        model=prefs.model,
        aspect_ratio=prefs.aspect_ratio,
        resolution=prefs.resolution,
        duration_seconds=prefs.duration_seconds,
        style=prefs.style,
        camera_motion=prefs.camera_motion,
    )
    state_store.set_draft(user_id, draft)
    await state.set_state(VideoGenStates.confirming_generation)

    await wait_msg.edit_text(
        _format_draft_preview(draft, is_optimized=True, note_vi=opt_res.explanation_vi),
        parse_mode="HTML",
        reply_markup=build_confirm_generation_kb(is_optimized=True),
    )


# ==============================================================================
# 6. DRAFT CONFIRMATION, OPTIMIZATION TOGGLE & TASK EXECUTION
# ==============================================================================


@router.callback_query(F.data == "gen:optimize_draft")
async def cb_optimize_existing_draft(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    draft = state_store.get_draft(user_id)
    if not draft:
        await callback.answer("⚠️ Bản nháp đã hết hạn, vui lòng nhập lại.", show_alert=True)
        return

    if callback.message:
        await callback.message.edit_text("✨ <i>Đang tối ưu lại Prompt bằng Gemini AI...</i>", parse_mode="HTML")

    opt_res = await prompt_service.optimize_prompt(
        raw_prompt=draft.original_prompt,
        style_key=draft.style,
        camera_key=draft.camera_motion,
        is_image_to_video=(draft.generation_type == "image_to_video"),
    )
    draft.final_prompt = opt_res.optimized_prompt
    draft.negative_prompt = opt_res.negative_prompt

    if callback.message:
        await callback.message.edit_text(
            _format_draft_preview(draft, is_optimized=True, note_vi=opt_res.explanation_vi),
            parse_mode="HTML",
            reply_markup=build_confirm_generation_kb(is_optimized=True),
        )
    await callback.answer("✨ Đã tối ưu Prompt!")


@router.callback_query(F.data == "gen:use_original")
async def cb_use_original_prompt(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    draft = state_store.get_draft(user_id)
    if not draft:
        await callback.answer("⚠️ Bản nháp đã hết hạn, vui lòng nhập lại.", show_alert=True)
        return

    draft.final_prompt = prompt_service.build_styled_prompt(
        base_prompt=draft.original_prompt,
        style_key=draft.style,
        camera_key=draft.camera_motion,
    )
    if callback.message:
        await callback.message.edit_text(
            _format_draft_preview(draft, is_optimized=False),
            parse_mode="HTML",
            reply_markup=build_confirm_generation_kb(is_optimized=False),
        )
    await callback.answer("↩️ Đã chuyển về Prompt gốc!")


@router.callback_query(F.data == "gen:confirm")
async def cb_confirm_and_enqueue(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    user_id = callback.from_user.id
    active_list = state_store.get_user_active_tasks(user_id)
    if len(active_list) >= settings.MAX_CONCURRENT_TASKS:
        await callback.answer(
            f"⚠️ Bạn đang có {len(active_list)} video đang xử lý cùng lúc. Vui lòng đợi hoàn tất hoặc hủy bớt!",
            show_alert=True,
        )
        return

    draft = state_store.pop_draft(user_id)
    if not draft:
        await callback.answer("⚠️ Yêu cầu này đã được gửi hoặc đã hết hạn.", show_alert=True)
        return

    await state.clear()

    if callback.message:
        await callback.message.edit_text(
            f"🚀 <b>Đã đưa tác vụ #{draft.task_id} vào hàng đợi xử lý!</b>\n"
            f"• <b>Thông số:</b> <code>{draft.aspect_ratio} | {draft.resolution} | {draft.duration_seconds}s</code>\n"
            f"• <b>Trạng thái:</b> <code>Pending...</code>",
            parse_mode="HTML",
            reply_markup=build_cancel_task_kb(draft.task_id),
        )
        draft.status_message_id = callback.message.message_id

    task_runner.submit(bot, draft)
    await callback.answer("🎬 Bắt đầu tạo video!")


# ==============================================================================
# 7. ACTIVE TASKS & CANCELLATION
# ==============================================================================


@router.callback_query(F.data == "menu:active_tasks")
async def cb_view_active_tasks(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    tasks = state_store.get_user_active_tasks(user_id)

    if not tasks:
        if callback.message:
            await callback.message.edit_text(
                "📋 <b>TÁC VỤ ĐANG XỬ LÝ</b>\n\nHiện không có tác vụ tạo video nào đang chạy.",
                parse_mode="HTML",
                reply_markup=build_back_to_menu_kb(),
            )
        await callback.answer()
        return

    lines = ["📋 <b>DANH SÁCH TÁC VỤ ĐANG CHẠY:</b>\n"]
    for t in tasks:
        lines.append(
            f"• <b>Mã #{t.task_id}</b> | <code>{t.status.value.upper()}</code> | "
            f"<code>{t.aspect_ratio} {t.resolution} {t.duration_seconds}s</code>\n"
            f"  <i>{html.escape(t.original_prompt[:80])}</i>"
        )

    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=build_back_to_menu_kb(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("task:cancel:"))
async def cb_cancel_task(callback: CallbackQuery) -> None:
    task_id = (callback.data or "").split(":", 2)[2]
    cancelled = state_store.request_cancel(task_id, callback.from_user.id)
    if cancelled:
        await callback.answer(f"🛑 Đã gửi lệnh hủy tác vụ #{task_id}!", show_alert=True)
        if callback.message:
            await callback.message.edit_text(
                f"🛑 <b>Đang hủy tác vụ #{task_id}...</b>",
                parse_mode="HTML",
                reply_markup=build_main_menu_kb(),
            )
    else:
        await callback.answer("ℹ️ Tác vụ này đã hoàn tất hoặc không còn tồn tại.", show_alert=True)


# ==============================================================================
# 8. DEFAULT DIRECT TEXT HANDLER (QUICK TEXT-TO-VIDEO)
# ==============================================================================


@router.message(F.text)
async def handle_direct_text_message(message: Message, state: FSMContext) -> None:
    """Allow personal user to simply type any prompt in chat without clicking menu first."""
    await _prepare_text_video_draft(message, state)

