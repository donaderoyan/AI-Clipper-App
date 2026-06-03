import os
import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from collections import deque


def calculate_crop(video_path: Path, aspect_ratio: str, start: float = 0.0, end: float = 0.0) -> Tuple[int, int, int, int]:
    """
    Analyzes video and returns optimal crop coordinates for smart panning.
    Menggunakan speaker detection untuk multi-speaker scenarios.
    
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
    
    mouth_cascade_path = cv2.data.haarcascades + 'haarcascade_mcs_mouth.xml'
    if not os.path.exists(mouth_cascade_path):
        mouth_cascade_path = cv2.data.haarcascades + 'haarcascade_smile.xml'
    mouth_cascade = cv2.CascadeClassifier(mouth_cascade_path)

    # Use new speaker detection analysis
    focus_positions = _analyze_frames_with_speaker_detection(
        capture,
        width,
        height,
        target_width,
        target_height,
        face_cascade,
        eye_cascade,
        mouth_cascade,
        start,
        end,
        fps,
    )

    capture.release()

    if focus_positions:
        crop_x, crop_y = _average_crop_positions([(x, y) for _, x, y in focus_positions])
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
    Menggunakan speaker detection untuk multi-speaker scenarios.
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
    
    mouth_cascade_path = cv2.data.haarcascades + 'haarcascade_mcs_mouth.xml'
    if not os.path.exists(mouth_cascade_path):
        mouth_cascade_path = cv2.data.haarcascades + 'haarcascade_smile.xml'
    mouth_cascade = cv2.CascadeClassifier(mouth_cascade_path)

    # Use new speaker detection analysis
    crop_positions = _analyze_frames_with_speaker_detection(
        capture,
        width,
        height,
        target_width,
        target_height,
        face_cascade,
        eye_cascade,
        mouth_cascade,
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
            # If no faces detected at all, try to fall back to prominent region
            if len(faces) == 0:
                object_center = _detect_prominent_region(frame, frame_area)
                if object_center is not None:
                    best_focus_x, best_focus_y = object_center
                    best_confidence = 0.75
            else:
                # Faces were detected but scoring failed; fallback to first face center
                fx, fy, fw, fh = faces[0]
                best_focus_x = fx + fw // 2
                best_focus_y = fy + fh // 2
                best_confidence = 0.5

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
    window_size: int = 3,  # Reduced from 5 untuk panning lebih cepat
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


# ============================================================================
# SPEAKER DETECTION FUNCTIONS - Multi-Speaker Mouth Activity Detection
# ============================================================================


class FaceTracker:
    """Track face identity across frames untuk deteksi speaker yang konsisten"""
    
    def __init__(self, max_distance_threshold: float = 100.0):
        self.max_distance_threshold = max_distance_threshold
        self.face_ids: Dict[int, deque] = {}
        self.next_id = 0
        self.id_history_size = 5
    
    def update_faces(self, faces: List[Tuple[int, int, int, int]]) -> List[Tuple[int, Tuple[int, int, int, int]]]:
        """
        Match detections dengan existing face IDs atau buat ID baru.
        Returns: [(face_id, (x, y, w, h)), ...]
        """
        if not faces:
            return []
        
        current_centers = [(x + w//2, y + h//2) for x, y, w, h in faces]
        matched_faces = []
        used_indices = set()
        
        # Try to match dengan existing face IDs
        for face_id, history in list(self.face_ids.items()):
            if not history:
                continue
            
            last_x, last_y = history[-1]
            best_distance = float('inf')
            best_idx = -1
            
            for idx, (cx, cy) in enumerate(current_centers):
                if idx in used_indices:
                    continue
                
                distance = ((cx - last_x) ** 2 + (cy - last_y) ** 2) ** 0.5
                
                if distance < best_distance and distance <= self.max_distance_threshold:
                    best_distance = distance
                    best_idx = idx
            
            if best_idx >= 0:
                used_indices.add(best_idx)
                x, y, w, h = faces[best_idx]
                history.append((x + w//2, y + h//2))
                if len(history) > self.id_history_size:
                    history.popleft()
                matched_faces.append((face_id, faces[best_idx]))
        
        # Assign new IDs untuk unmatched detections
        for idx, face in enumerate(faces):
            if idx not in used_indices:
                self.face_ids[self.next_id] = deque([(face[0] + face[2]//2, face[1] + face[3]//2)])
                matched_faces.append((self.next_id, face))
                self.next_id += 1
        
        # Cleanup IDs yang sudah tidak terdeteksi
        self.face_ids = {
            fid: hist for fid, hist in self.face_ids.items() 
            if fid in [mid for mid, _ in matched_faces]
        }
        
        return sorted(matched_faces, key=lambda x: x[0])


def _detect_mouth_activity(
    prev_gray: Optional[np.ndarray],
    curr_gray: np.ndarray,
    face_box: Tuple[int, int, int, int],
    mouth_cascade,
) -> float:
    """
    Deteksi aktivitas mulut dalam face ROI.
    Returns confidence score (0.0 - 2.0) berdasarkan mouth detection dan size.
    """
    fx, fy, fw, fh = face_box
    h_frame, w_frame = curr_gray.shape[:2]

    # Mouth biasanya berada di 50-85% dari tinggi wajah
    mouth_y_start = max(0, fy + int(fh * 0.5))
    mouth_y_end = min(h_frame, fy + int(fh * 0.85))
    mouth_x_start = max(0, fx)
    mouth_x_end = min(w_frame, fx + fw)

    # Crop from curr_gray for cascade detection with bounds checking
    if mouth_y_end <= mouth_y_start or mouth_x_end <= mouth_x_start:
        return 0.4  # ROI too small, return low confidence
    
    mouth_roi = curr_gray[mouth_y_start:mouth_y_end, mouth_x_start:mouth_x_end]

    # If mouth cascade is not available or ROI is empty, fallback to optical flow
    try:
        mouths = []
        if mouth_cascade is not None and not getattr(mouth_cascade, 'empty', lambda: False)():
            mouths = mouth_cascade.detectMultiScale(
                mouth_roi,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(15, 10),
                maxSize=(int(fw * 0.6), int(fh * 0.3)),
            )

        if len(mouths) > 0:
            # Deteksi multiple mouths bisa berarti mulut terbuka (aktivitas)
            mouth_activity = min(2.0, len(mouths) * 0.8)
            mouth_areas = [mw * mh for (_, _, mw, mh) in mouths]
            max_mouth_area = max(mouth_areas)
            area_confidence = min(2.0, (max_mouth_area / (fw * fh * 0.1)) * 0.5)
            mouth_activity = max(mouth_activity, area_confidence)
            return mouth_activity
    except Exception:
        # If cascade fails for some reason, continue to optical-flow fallback
        mouths = []

    # Optical flow fallback: measure motion in mouth ROI between prev and curr frames
    if prev_gray is not None:
        roi = (mouth_x_start, mouth_y_start, mouth_x_end - mouth_x_start, max(1, mouth_y_end - mouth_y_start))
        flow_mag = _calculate_optical_flow_magnitude(prev_gray, curr_gray, roi)
        # scale to mouth score range (0.0 - 2.0)
        return min(2.0, flow_mag * 2.0 + 0.3)

    # No prev frame and no mouth detections: low confidence
    return 0.4


def _calculate_optical_flow_magnitude(
    prev_frame: np.ndarray,
    curr_frame: np.ndarray,
    roi: Tuple[int, int, int, int],
) -> float:
    """
    Hitung magnitude optical flow dalam ROI untuk deteksi pergerakan.
    Returns: average magnitude (normalized 0.0-1.0)
    """
    x, y, w, h = roi
    roi_prev = prev_frame[y:y+h, x:x+w]
    roi_curr = curr_frame[y:y+h, x:x+w]
    
    if roi_prev.size == 0 or roi_curr.size == 0:
        return 0.0
    
    try:
        flow = cv2.calcOpticalFlowFarneback(
            roi_prev, roi_curr,
            None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        
        magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
        avg_magnitude = np.mean(magnitude)
        
        # Normalize ke 0-1 range
        return min(1.0, avg_magnitude / 2.0)
    except Exception:
        return 0.0


def _detect_speaker_face(
    frame: np.ndarray,
    prev_frame: Optional[np.ndarray],
    faces_with_ids: List[Tuple[int, Tuple[int, int, int, int]]],
    face_cascade,
    eye_cascade,
    mouth_cascade,
) -> Tuple[Optional[Tuple[int, int]], float]:
    """
    Deteksi face yang sedang berbicara (speaker) berdasarkan:
    1. Eye detection confidence (prioritas utama)
    2. Mouth activity (tiebreaker untuk multiple faces)
    3. Optical flow magnitude (fallback)
    
    Returns: (speaker_focus_point, speaker_confidence)
    """
    if not faces_with_ids:
        return None, 0.0
    
    speaker_id = -1
    highest_score = 0.0
    speaker_focus = None
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Collect scores for all faces
    face_scores = []
    
    for face_id, (fx, fy, fw, fh) in faces_with_ids:
        face_roi = gray[fy:fy+fh, fx:fx+fw]
        
        # 1. Eye detection score (indikasi wajah terdeteksi dengan baik - PRIORITAS UTAMA)
        eyes = eye_cascade.detectMultiScale(
            face_roi,
            scaleFactor=1.05,
            minNeighbors=5,
            minSize=(15, 15),
        )
        
        eye_score = 0.0
        focus_x = fx + fw // 2
        focus_y = fy + fh // 2
        
        if len(eyes) >= 2:
            eye_score = 2.0
            eye_centers_x = [ex + ew // 2 for (ex, ey, ew, eh) in eyes[:2]]
            eye_centers_y = [ey + eh // 2 for (ex, ey, ew, eh) in eyes[:2]]
            focus_x = fx + int(sum(eye_centers_x) / len(eye_centers_x))
            focus_y = fy + int(sum(eye_centers_y) / len(eye_centers_y))
        elif len(eyes) == 1:
            eye_score = 1.5
            ex, ey, ew, eh = eyes[0]
            focus_x = fx + ex + ew // 2
            focus_y = fy + ey + eh // 2
        else:
            eye_score = 0.7  # Reduced from 0.5, kurang reliable
        
        # 2. Mouth activity score (use prev frame for optical-flow fallback)
        mouth_score = _detect_mouth_activity(prev_frame, gray, (fx, fy, fw, fh), mouth_cascade)
        
        # 3. Optical flow score (pergerakan dalam wajah)
        flow_score = 0.0
        if prev_frame is not None:
            flow_score = _calculate_optical_flow_magnitude(prev_frame, frame, (fx, fy, fw, fh)) * 1.5
        
        # IMPROVED SCORING: Prioritas eye detection, mouth/flow sebagai tiebreaker
        # Jika eye_score tinggi (2.0 = kedua mata), prioritas tinggi regardless mouth
        # Jika eye_score rendah, gunakan mouth+flow untuk differentiate
        if eye_score >= 2.0:
            # Strong face (both eyes detected) - high priority
            total_score = 3.0 + (mouth_score * 0.3) + (flow_score * 0.1)
        elif eye_score >= 1.5:
            # Good face (one eye detected) - medium priority
            total_score = 2.0 + (mouth_score * 0.4) + (flow_score * 0.2)
        else:
            # Weak face (no clear eyes) - low priority
            total_score = (eye_score * 0.5) + (mouth_score * 0.3) + (flow_score * 0.2)
        
        face_scores.append((total_score, face_id, focus_x, focus_y))
    
    # Select face dengan highest score
    if face_scores:
        face_scores.sort(key=lambda x: x[0], reverse=True)
        highest_score, speaker_id, focus_x, focus_y = face_scores[0]
        speaker_focus = (focus_x, focus_y)
    
    return speaker_focus, highest_score


def _analyze_frames_with_speaker_detection(
    capture: cv2.VideoCapture,
    frame_width: int,
    frame_height: int,
    target_width: int,
    target_height: int,
    face_cascade,
    eye_cascade,
    mouth_cascade,
    start: float,
    end: float,
    fps: float,
) -> List[Tuple[int, int, int]]:
    """
    Analyze video frames dengan speaker detection untuk multi-speaker scenarios.
    Prioritizes face yang sedang berbicara (mouth activity + optical flow).
    """
    frame_area = frame_width * frame_height
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(start * fps)
    end_frame = int(end * fps) if end > 0 else total_frames
    end_frame = min(end_frame, total_frames)

    max_sample_frames = 180  # Increased dari 120 untuk panning lebih responsif
    frame_step = 1
    if end_frame - start_frame > max_sample_frames:
        frame_step = max(1, (end_frame - start_frame) // max_sample_frames)

    focus_points = []
    current_frame = start_frame
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    face_tracker = FaceTracker()
    prev_frame_gray = None

    while current_frame < end_frame:
        ret, frame = capture.read()
        if not ret:
            break

        if (current_frame - start_frame) % frame_step != 0:
            current_frame += 1
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
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
            # Track faces dan assign IDs
            faces_with_ids = face_tracker.update_faces(list(faces))
            
            # Deteksi speaker dalam faces
            speaker_focus, speaker_score = _detect_speaker_face(
                frame, prev_frame_gray, faces_with_ids,
                face_cascade, eye_cascade, mouth_cascade
            )
            
            if speaker_focus and speaker_score > 0:
                best_focus_x, best_focus_y = speaker_focus
                best_confidence = speaker_score
            else:
                # Fallback ke old logic jika speaker detection gagal
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
        prev_frame_gray = gray.copy()
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


