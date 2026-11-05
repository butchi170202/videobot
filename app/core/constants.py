"""Official Google Veo / Gemini API constants and video parameter definitions."""

from enum import StrEnum


class VideoModel(StrEnum):
    """Supported official Google Veo video generation models."""

    VEO_3_1_FAST = "veo-3.1-fast-generate-preview"
    VEO_3_1_STANDARD = "veo-3.1-generate-preview"
    VEO_2_0 = "veo-2.0-generate-001"


MODEL_LABELS: dict[str, str] = {
    VideoModel.VEO_3_1_FAST: "⚡ Veo 3.1 Fast (Nhanh + Có âm thanh)",
    VideoModel.VEO_3_1_STANDARD: "🎬 Veo 3.1 Pro (Chất lượng cao nhất)",
    VideoModel.VEO_2_0: "🎞️ Veo 2.0 (Bản tiêu chuẩn không âm thanh)",
}

# Tỷ lệ khung hình thực tế được Veo API hỗ trợ trực tiếp
SUPPORTED_ASPECT_RATIOS: dict[str, str] = {
    "16:9": "🖥️ 16:9 (Ngang - YouTube/PC)",
    "9:16": "📱 9:16 (Dọc - TikTok/Reels/Shorts)",
}

# Độ phân giải thực tế được Veo 3.1 hỗ trợ
SUPPORTED_RESOLUTIONS: dict[str, str] = {
    "720p": "HD 720p (Nhanh & Tiết kiệm)",
    "1080p": "Full HD 1080p (Yêu cầu thời lượng 8s)",
}

# Thời lượng video thực tế được Veo 3.1 hỗ trợ (tính bằng giây)
SUPPORTED_DURATIONS: list[int] = [4, 6, 8]

# Phong cách hình ảnh (Tích hợp vào Prompt / AI Prompt Optimizer)
VIDEO_STYLES: dict[str, str] = {
    "cinematic": "🎬 Cinematic (Điện ảnh)",
    "realistic": "📷 Realistic (Chân thực)",
    "3d_animation": "🧊 3D Animation (Hoạt hình 3D Pixar/Unreal)",
    "anime": "🌸 Anime (Hoạt hình Nhật Bản)",
    "documentary": "🌍 Documentary (Phim tài liệu tự nhiên)",
}

STYLE_PROMPT_DESCRIPTIONS: dict[str, str] = {
    "cinematic": (
        "Cinematic film look, anamorphic lens, dramatic volumetric lighting, "
        "shallow depth of field, rich color grading, 35mm film grain"
    ),
    "realistic": (
        "Photorealistic, ultra-detailed natural lighting, lifelike textures, "
        "physically accurate motion, raw camera footage aesthetic"
    ),
    "3d_animation": (
        "High-end 3D feature animation style, Pixar and Unreal Engine 5 render quality, "
        "subsurface scattering, vibrant expressive lighting, smooth character motion"
    ),
    "anime": (
        "High-production theatrical anime style, Makoto Shinkai inspired lighting, "
        "detailed hand-drawn background art, fluid dynamic animation"
    ),
    "documentary": (
        "National Geographic / BBC Earth nature documentary style, crisp telephoto lens, "
        "authentic natural environment, crystal clear detail"
    ),
}

# Chuyển động camera (Tích hợp vào Prompt / AI Prompt Optimizer)
CAMERA_MOTIONS: dict[str, str] = {
    "static": "📍 Static (Cố định khung hình)",
    "tracking": "🏃 Tracking (Bám theo chủ thể)",
    "dolly": "🚂 Dolly In/Out (Đẩy máy tiến/lùi mượt mà)",
    "pan": "↔️ Slow Pan (Lia máy ngang chậm rãi)",
    "zoom": "🔍 Smooth Zoom (Thu phóng tiêu cự)",
}

CAMERA_PROMPT_DESCRIPTIONS: dict[str, str] = {
    "static": "locked-off static tripod shot, stable framing",
    "tracking": "smooth gimbal tracking shot following the main subject seamlessly",
    "dolly": "slow cinematic dolly push-in shot creating depth and immersion",
    "pan": "smooth horizontal camera pan revealing the scene naturally",
    "zoom": "gradual optical zoom focusing attention on the main subject",
}

DEFAULT_NEGATIVE_PROMPT: str = (
    "blurry, low quality, distorted anatomy, extra limbs, morphing objects, "
    "unnatural physics, flickering frames, watermark, text overlay, jittery motion"
)


class TaskStatus(StrEnum):
    """Status lifecycle of an active video generation task."""

    PENDING = "pending"
    PROCESSING = "processing"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

