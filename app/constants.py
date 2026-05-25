from enum import Enum

IMAGE_FORMATS = {"jpg", "jpeg", "png", "webp", "bmp"}
VIDEO_FORMATS = {"mp4", "mkv", "mov", "avi"}
IMAGE_SIZE_PRESETS = [128, 256, 512, 768, 1024, 2048]
THUMBNAIL_SIZE = 96


class ItemStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class FileType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class PayloadMode(str, Enum):
    AUTO = "auto"
    DATA_URI = "data_uri"
    RAW_BASE64 = "raw_base64"


class VideoMode(str, Enum):
    FRAME_EXTRACTION = "frame_extraction"
    NATIVE_VIDEO = "native_video"


class OverwritePolicy(str, Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    ASK_BATCH = "ask_batch"


class FrameExtractionMode(str, Enum):
    EVERY_N_SECONDS = "every_n_seconds"
    EVERY_N_FRAMES = "every_n_frames"
    MAX_N_FRAMES = "max_n_frames"
