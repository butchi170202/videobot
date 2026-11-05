"""Inline Keyboards for the Telegram AI Video Generator Bot."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.constants import (
    CAMERA_MOTIONS,
    MODEL_LABELS,
    SUPPORTED_ASPECT_RATIOS,
    SUPPORTED_DURATIONS,
    SUPPORTED_RESOLUTIONS,
    VIDEO_STYLES,
)
from app.core.state_store import UserPreferences


def build_main_menu_kb() -> InlineKeyboardMarkup:
    """Build the main personal bot Inline Keyboard menu."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎬 Tạo video từ văn bản", callback_data="menu:text_to_video"),
        InlineKeyboardButton(text="🖼️ Tạo video từ hình ảnh", callback_data="menu:image_to_video"),
    )
    builder.row(
        InlineKeyboardButton(text="✍️ Tối ưu Prompt bằng AI", callback_data="menu:optimize_prompt"),
        InlineKeyboardButton(text="⚙️ Cài đặt thông số video", callback_data="menu:settings"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Tác vụ đang xử lý", callback_data="menu:active_tasks"),
        InlineKeyboardButton(text="❓ Hướng dẫn sử dụng", callback_data="menu:help"),
    )
    return builder.as_markup()


def build_back_to_menu_kb() -> InlineKeyboardMarkup:
    """Simple button to return to the main menu and cancel current input."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Quay về Menu chính", callback_data="menu:home"))
    return builder.as_markup()


def build_confirm_generation_kb(is_optimized: bool = False) -> InlineKeyboardMarkup:
    """Build confirmation keyboard before submitting job to Google Veo API."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚀 Xác nhận tạo Video ngay", callback_data="gen:confirm"),
    )
    if not is_optimized:
        builder.row(
            InlineKeyboardButton(
                text="✨ Dùng AI tối ưu lại Prompt này",
                callback_data="gen:optimize_draft",
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="↩️ Dùng lại Prompt gốc ban đầu",
                callback_data="gen:use_original",
            )
        )
    builder.row(
        InlineKeyboardButton(text="⚙️ Đổi cài đặt video", callback_data="menu:settings"),
        InlineKeyboardButton(text="❌ Hủy bỏ", callback_data="menu:home"),
    )
    return builder.as_markup()


def build_cancel_task_kb(task_id: str) -> InlineKeyboardMarkup:
    """Build button allowing the user to cancel an active video generation task."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🛑 Hủy tác vụ này", callback_data=f"task:cancel:{task_id}")
    )
    return builder.as_markup()


def build_settings_overview_kb(prefs: UserPreferences) -> InlineKeyboardMarkup:
    """Build interactive video parameter configuration keyboard."""
    builder = InlineKeyboardBuilder()
    opt_label = "BẬT ✅" if prefs.auto_optimize_prompt else "TẮT ❌"

    builder.row(
        InlineKeyboardButton(
            text=f"📐 Tỷ lệ: {prefs.aspect_ratio}",
            callback_data="set_menu:aspect_ratio",
        ),
        InlineKeyboardButton(
            text=f"🎞️ Độ phân giải: {prefs.resolution}",
            callback_data="set_menu:resolution",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=f"⏱️ Thời lượng: {prefs.duration_seconds} giây",
            callback_data="set_menu:duration",
        ),
        InlineKeyboardButton(
            text=f"🎨 Phong cách: {VIDEO_STYLES.get(prefs.style, prefs.style).split()[1]}",
            callback_data="set_menu:style",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🎥 Camera: {CAMERA_MOTIONS.get(prefs.camera_motion, prefs.camera_motion).split()[1]}",
            callback_data="set_menu:camera",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🤖 Model: {MODEL_LABELS.get(prefs.model, prefs.model)}",
            callback_data="set_menu:model",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"✨ Tự động tối ưu Prompt bằng AI: {opt_label}",
            callback_data="set_val:toggle_optimize",
        )
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Quay về Menu chính", callback_data="menu:home")
    )
    return builder.as_markup()


def build_sub_setting_kb(category: str, current_value: str | int) -> InlineKeyboardMarkup:
    """Build selection keyboard for a specific video setting category."""
    builder = InlineKeyboardBuilder()

    if category == "aspect_ratio":
        for key, label in SUPPORTED_ASPECT_RATIOS.items():
            mark = "✅ " if key == current_value else ""
            builder.row(
                InlineKeyboardButton(
                    text=f"{mark}{label}",
                    callback_data=f"set_val:aspect_ratio:{key}",
                )
            )
    elif category == "resolution":
        for key, label in SUPPORTED_RESOLUTIONS.items():
            mark = "✅ " if key == current_value else ""
            builder.row(
                InlineKeyboardButton(
                    text=f"{mark}{label}",
                    callback_data=f"set_val:resolution:{key}",
                )
            )
    elif category == "duration":
        for sec in SUPPORTED_DURATIONS:
            mark = "✅ " if int(current_value) == sec else ""
            builder.row(
                InlineKeyboardButton(
                    text=f"{mark}{sec} giây",
                    callback_data=f"set_val:duration:{sec}",
                )
            )
    elif category == "style":
        for key, label in VIDEO_STYLES.items():
            mark = "✅ " if key == current_value else ""
            builder.row(
                InlineKeyboardButton(
                    text=f"{mark}{label}",
                    callback_data=f"set_val:style:{key}",
                )
            )
    elif category == "camera":
        for key, label in CAMERA_MOTIONS.items():
            mark = "✅ " if key == current_value else ""
            builder.row(
                InlineKeyboardButton(
                    text=f"{mark}{label}",
                    callback_data=f"set_val:camera:{key}",
                )
            )
    elif category == "model":
        for key, label in MODEL_LABELS.items():
            mark = "✅ " if key == current_value else ""
            builder.row(
                InlineKeyboardButton(
                    text=f"{mark}{label}",
                    callback_data=f"set_val:model:{key}",
                )
            )

    builder.row(
        InlineKeyboardButton(text="⬅️ Quay lại Cài đặt", callback_data="menu:settings")
    )
    return builder.as_markup()

