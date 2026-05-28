import cv2
from pathlib import Path
from typing import Tuple


def calculate_crop(video_path: Path, aspect_ratio: str) -> Tuple[int, int, int, int]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Gagal membuka video untuk analisis: {video_path}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()

    if aspect_ratio == "9:16":
        target_width = min(width, int(height * 9 / 16))
        target_height = height
        x = max(0, (width - target_width) // 2)
        y = 0
        return target_width, target_height, x, y

    if aspect_ratio == "16:9":
        target_height = min(height, int(width * 9 / 16))
        target_width = width
        x = 0
        y = max(0, (height - target_height) // 2)
        return target_width, target_height, x, y

    return width, height, 0, 0
