import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple


def calculate_crop(video_path: Path, aspect_ratio: str, start: float = 0.0, end: float = 0.0) -> Tuple[int, int, int, int]:
    """
    Analyzes video and returns optimal crop coordinates for smart panning.
    
    Args:
        video_path: Path to the video file
        aspect_ratio: Target aspect ratio ("9:16" or "16:9")
        start: Start time in seconds (0 = beginning)
        end: End time in seconds (0 = full video)
    
    Returns:
        Tuple of (target_width, target_height, crop_x, crop_y)
    """
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Gagal membuka video untuk analisis: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Calculate target dimensions
    if aspect_ratio == "9:16":
        target_width = min(width, int(height * 9 / 16))
        target_height = height
    elif aspect_ratio == "16:9":
        target_height = min(height, int(width * 16 / 9))
        target_width = width
        if target_height > height:
            target_height = height
            target_width = int(height * 16 / 9)
    else:
        capture.release()
        return width, height, 0, 0

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    focus_positions = _analyze_frames_with_tracking(
        capture,
        width,
        height,
        target_width,
        target_height,
        face_cascade,
        eye_cascade,
        start,
        end,
        fps,
    )

    capture.release()

    if focus_positions:
        crop_x, crop_y = _average_crop_positions(focus_positions)
        return target_width, target_height, crop_x, crop_y

    crop_x = max(0, (width - target_width) // 2)
    crop_y = max(0, (height - target_height) // 2)
    return target_width, target_height, crop_x, crop_y


def calculate_crop_path(
    video_path: Path,
    aspect_ratio: str,
    start: float = 0.0,
    end: float = 0.0,
) -> Tuple[int, int, List[Tuple[int, int, int]]]:
    """
    Returns a list of crop positions for frame-by-frame smart panning.
    Each position is (frame_index, crop_x, crop_y).
    """
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Gagal membuka video untuk analisis: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if aspect_ratio == "9:16":
        target_width = min(width, int(height * 9 / 16))
        target_height = height
    elif aspect_ratio == "16:9":
        target_height = min(height, int(width * 16 / 9))
        target_width = width
        if target_height > height:
            target_height = height
            target_width = int(height * 16 / 9)
    else:
        capture.release()
        return width, height, []

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    crop_positions = _analyze_frames_with_tracking(
        capture,
        width,
        height,
        target_width,
        target_height,
        face_cascade,
        eye_cascade,
        start,
        end,
        fps,
    )
    capture.release()

    if crop_positions:
        return target_width, target_height, crop_positions

    center_x = max(0, (width - target_width) // 2)
    center_y = max(0, (height - target_height) // 2)
    return target_width, target_height, [(0, center_x, center_y)]


def _analyze_frames_with_tracking(
    capture: cv2.VideoCapture,
    frame_width: int,
    frame_height: int,
    target_width: int,
    target_height: int,
    face_cascade,
    eye_cascade,
    start: float,
    end: float,
    fps: float,
) -> List[Tuple[int, int]]:
    """
    Analyze video frames to detect faces, eyes, and prominent objects.
    """
    frame_area = frame_width * frame_height
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(start * fps)
    end_frame = int(end * fps) if end > 0 else total_frames
    end_frame = min(end_frame, total_frames)

    max_sample_frames = 120
    frame_step = 1
    if end_frame - start_frame > max_sample_frames:
        frame_step = max(1, (end_frame - start_frame) // max_sample_frames)

    focus_points = []
    current_frame = start_frame
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    while current_frame < end_frame:
        ret, frame = capture.read()
        if not ret:
            break

        if (current_frame - start_frame) % frame_step != 0:
            current_frame += 1
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        best_focus_x = frame_width // 2
        best_focus_y = frame_height // 2
        best_confidence = 0.0

        if len(faces) > 0:
            for (fx, fy, fw, fh) in faces:
                face_roi = gray[fy : fy + fh, fx : fx + fw]
                eyes = eye_cascade.detectMultiScale(
                    face_roi,
                    scaleFactor=1.05,
                    minNeighbors=5,
                    minSize=(15, 15),
                )

                if len(eyes) >= 2:
                    eye_centers_x = [ex + ew // 2 for (ex, ey, ew, eh) in eyes[:2]]
                    eye_centers_y = [ey + eh // 2 for (ex, ey, ew, eh) in eyes[:2]]
                    focus_x = fx + int(sum(eye_centers_x) / len(eye_centers_x))
                    focus_y = fy + int(sum(eye_centers_y) / len(eye_centers_y))
                    confidence = 2.0
                elif len(eyes) == 1:
                    ex, ey, ew, eh = eyes[0]
                    focus_x = fx + ex + ew // 2
                    focus_y = fy + ey + eh // 2
                    confidence = 1.5
                else:
                    focus_x = fx + fw // 2
                    focus_y = fy + fh // 2
                    confidence = 1.0

                if confidence > best_confidence:
                    best_focus_x = focus_x
                    best_focus_y = focus_y
                    best_confidence = confidence

        if best_confidence == 0.0:
            object_center = _detect_prominent_region(frame, frame_area)
            if object_center is not None:
                best_focus_x, best_focus_y = object_center
                best_confidence = 0.75

        focus_points.append((current_frame - start_frame, best_focus_x, best_focus_y))
        current_frame += 1

    smoothed_focus = _smooth_trajectory(focus_points, window_size=5)
    crop_positions = []
    for frame_idx, focus_x, focus_y in smoothed_focus:
        crop_x = focus_x - (target_width // 2)
        crop_y = focus_y - (target_height // 2)
        crop_x = max(0, min(crop_x, frame_width - target_width))
        crop_y = max(0, min(crop_y, frame_height - target_height))
        crop_positions.append((frame_idx, crop_x, crop_y))

    return crop_positions


def _detect_prominent_region(frame: np.ndarray, frame_area: int) -> Optional[Tuple[int, int]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7, 7), 0)
    edges = cv2.Canny(blur, 50, 150)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    closed = cv2.dilate(closed, kernel, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    min_area = max(int(frame_area * 0.02), 1200)
    candidates = [cnt for cnt in contours if cv2.contourArea(cnt) >= min_area]
    if not candidates:
        return None

    candidates = sorted(candidates, key=cv2.contourArea, reverse=True)[:3]
    weighted_x = 0.0
    weighted_y = 0.0
    total_weight = 0.0

    for cnt in candidates:
        area = cv2.contourArea(cnt)
        x, y, w, h = cv2.boundingRect(cnt)
        weighted_x += (x + w // 2) * area
        weighted_y += (y + h // 2) * area
        total_weight += area

    if total_weight == 0:
        return None

    return int(weighted_x / total_weight), int(weighted_y / total_weight)


def _smooth_trajectory(
    points: List[Tuple[int, int, int]],
    window_size: int = 5,
) -> List[Tuple[int, int, int]]:
    if len(points) <= window_size:
        return points

    smoothed = []
    for i in range(len(points)):
        start_idx = max(0, i - window_size // 2)
        end_idx = min(len(points), i + window_size // 2 + 1)
        window = points[start_idx:end_idx]
        frame_idx = points[i][0]
        avg_x = int(sum(p[1] for p in window) / len(window))
        avg_y = int(sum(p[2] for p in window) / len(window))
        smoothed.append((frame_idx, avg_x, avg_y))

    return smoothed


def _average_crop_positions(positions: List[Tuple[int, int]]) -> Tuple[int, int]:
    avg_x = int(sum(x for x, _ in positions) / len(positions))
    avg_y = int(sum(y for _, y in positions) / len(positions))
    return avg_x, avg_y


