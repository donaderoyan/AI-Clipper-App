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
    profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
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
        profile_cascade,
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
    profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
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
        profile_cascade,
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

    candidates = sorted(candidates, key=cv2.contourArea, reverse=True)
    
    # Hanya ambil 1 kandidat paling besar, jangan rata-ratakan dengan kandidat lain
    # Jika dirata-ratakan, kamera akan menyorot di tengah antara 2 objek (bug)
    best_cnt = candidates[0]
    x, y, w, h = cv2.boundingRect(best_cnt)
    
    return x + w // 2, y + h // 2


def _smooth_trajectory(
    points: List[Tuple[int, int, int]],
    window_size: int = 15,  # Dinaikkan ke 15 (setengah detik) untuk kestabilan ekstra
) -> List[Tuple[int, int, int]]:
    if len(points) <= 1:
        return points

    # Tahap 1: Median filter untuk menghilangkan noise deteksi 
    median_points = []
    for i in range(len(points)):
        start_idx = max(0, i - 5)
        end_idx = min(len(points), i + 6)
        window = points[start_idx:end_idx]
        frame_idx = points[i][0]
        
        sorted_x = sorted([p[1] for p in window])
        sorted_y = sorted([p[2] for p in window])
        med_x = sorted_x[len(sorted_x) // 2]
        med_y = sorted_y[len(sorted_y) // 2]
        median_points.append((frame_idx, med_x, med_y))

    # Tahap 2: EMA dengan Snap (Smart Panning)
    smoothed = []
    ema_x = float(median_points[0][1])
    ema_y = float(median_points[0][2])
    
    # Faktor kehalusan: semakin kecil semakin halus bergeraknya saat mengikuti orang berjalan
    alpha = 0.1 
    
    for frame_idx, mx, my in median_points:
        dist = ((mx - ema_x)**2 + (my - ema_y)**2)**0.5
        
        if dist > 150.0:
            # Jarak sangat jauh (ganti pembicara), SNAP seketika tanpa smoothing!
            ema_x = float(mx)
            ema_y = float(my)
        else:
            # Jarak dekat (orang bergerak pelan), ikuti dengan mulus
            ema_x = ema_x + alpha * (mx - ema_x)
            ema_y = ema_y + alpha * (my - ema_y)
            
        smoothed.append((frame_idx, int(ema_x), int(ema_y)))

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
    Deteksi aktivitas mulut menggunakan Net Optical Flow (Mouth Flow - Head Flow).
    """
    fx, fy, fw, fh = face_box
    
    if prev_gray is None:
        return 0.0

    # Area bawah wajah (mulut)
    mouth_y_start = max(0, fy + int(fh * 0.55))
    mouth_y_end = min(curr_gray.shape[0], fy + int(fh * 0.95))
    mouth_x_start = max(0, fx + int(fw * 0.15))
    mouth_x_end = min(curr_gray.shape[1], fx + int(fw * 0.85))

    mouth_roi = (mouth_x_start, mouth_y_start, mouth_x_end - mouth_x_start, max(1, mouth_y_end - mouth_y_start))
    
    # Area atas wajah (mata/dahi) untuk mengukur pergerakan kepala secara umum
    upper_roi = (fx, fy, fw, max(1, int(fh * 0.4)))
    
    flow_mouth = _calculate_optical_flow_magnitude(prev_gray, curr_gray, mouth_roi)
    flow_head = _calculate_optical_flow_magnitude(prev_gray, curr_gray, upper_roi)
    
    # Net Mouth Flow: Gerakan mulut dikurangi gerakan kepala
    # Jika orang bicara tanpa menggeleng, flow_mouth tinggi, flow_head rendah.
    # Jika orang cuma mengangguk (diam), flow_mouth dan flow_head sama-sama tinggi -> selisihnya 0.
    net_mouth_flow = max(0.0, flow_mouth - flow_head)
    
    # Skalakan hasilnya agar berada di rentang 0.0 - 2.0
    return min(2.0, net_mouth_flow * 3.0)


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
    active_speaker_id: int = -1,
    last_valid_focus_x: Optional[int] = None,
    last_valid_focus_y: Optional[int] = None,
) -> Tuple[Optional[Tuple[int, int]], float, int]:
    """
    Deteksi face yang sedang berbicara (speaker) berdasarkan:
    1. Eye detection confidence (prioritas utama)
    2. Mouth activity (tiebreaker untuk multiple faces)
    3. Optical flow magnitude (fallback)
    
    Returns: (speaker_focus_point, speaker_confidence, speaker_id)
    """
    if not faces_with_ids:
        return None, 0.0, -1
    
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
        
        # IMPROVED SCORING: Net Mouth Flow adalah indikator UTAMA berbicara.
        speaking_score = (mouth_score * 3.0) + (flow_score * 0.5)
        
        # HUKUMAN UNTUK OBJEK DIAM (DINDING): Haar cascade sering salah deteksi dinding sebagai wajah.
        # Wajah asli manusia (meski diam) selalu memiliki mikromotion (nafas, kedip, dll) > 0.05.
        # Dinding/poster benar-benar diam = 0.0.
        static_penalty = 0.0
        if flow_score < 0.05 and mouth_score < 0.05:
            static_penalty = 2.0  # Hukuman berat agar kamera tidak mengunci dinding!
            
        total_score = speaking_score + (eye_score * 0.2) - static_penalty
            
        # SPATIAL HYSTERESIS (Kestabilan Kunci Kamera)
        # Jangan bergantung pada `face_id` tracker karena cascade sering berkedip dan mengganti ID.
        # Bergantunglah pada posisi fisik wajah.
        is_active = False
        if last_valid_focus_x is not None:
            dist_to_last = ((focus_x - last_valid_focus_x)**2 + (focus_y - last_valid_focus_y)**2)**0.5
            if dist_to_last < 150.0:  # Jika objek ini ada di tempat orang yang terakhir kita sorot
                is_active = True
                
        if is_active:
            total_score += 2.5  # Bonus loyalitas yang sangat besar!
        
        face_scores.append((total_score, face_id, focus_x, focus_y))
    
    # Select face dengan highest score
    if face_scores:
        face_scores.sort(key=lambda x: x[0], reverse=True)
        highest_score, speaker_id, focus_x, focus_y = face_scores[0]
        speaker_focus = (focus_x, focus_y)
    
    return speaker_focus, highest_score, speaker_id


def _analyze_frames_with_speaker_detection(
    capture: cv2.VideoCapture,
    frame_width: int,
    frame_height: int,
    target_width: int,
    target_height: int,
    face_cascade,
    profile_cascade,
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
    active_speaker_id = -1
    last_valid_focus_x = None
    last_valid_focus_y = None

    while current_frame < end_frame:
        ret, frame = capture.read()
        if not ret:
            break

        if (current_frame - start_frame) % frame_step != 0:
            current_frame += 1
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Downscale for faster detection
        scale_factor = 640.0 / frame_width if frame_width > 640 else 1.0
        if scale_factor < 1.0:
            small_gray = cv2.resize(gray, (0, 0), fx=scale_factor, fy=scale_factor)
        else:
            small_gray = gray
        
        # 1. Frontal faces
        faces_frontal = face_cascade.detectMultiScale(
            small_gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE
        )
        faces_frontal = list(faces_frontal) if len(faces_frontal) > 0 else []

        # 2. Profile faces (Left facing)
        faces_profile_left = profile_cascade.detectMultiScale(
            small_gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE
        )
        faces_profile_left = list(faces_profile_left) if len(faces_profile_left) > 0 else []

        # 3. Profile faces (Right facing - require horizontal flip)
        gray_flipped = cv2.flip(small_gray, 1)
        faces_profile_right_flipped = profile_cascade.detectMultiScale(
            gray_flipped, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE
        )
        faces_profile_right = []
        if len(faces_profile_right_flipped) > 0:
            small_width = small_gray.shape[1]
            for (x, y, w, h) in faces_profile_right_flipped:
                # Flip bounding box back to original coordinates
                orig_x = small_width - (x + w)
                faces_profile_right.append((orig_x, y, w, h))
        
        # Combine all detections
        all_faces = faces_frontal + faces_profile_left + faces_profile_right
        
        # Group overlapping rectangles (Non-maximum suppression)
        # to avoid detecting the same face multiple times
        faces = []
        if len(all_faces) > 0:
            rects = [[int(x), int(y), int(w), int(h)] for x, y, w, h in all_faces]
            # Add duplicates to ensure groupRectangles keeps them (it requires weights/neighbors)
            rects = rects + rects 
            faces_grouped, _ = cv2.groupRectangles(rects, 1, 0.2)
            
            # Upscale coordinates back to original size
            if scale_factor < 1.0:
                faces = [(int(x / scale_factor), int(y / scale_factor), int(w / scale_factor), int(h / scale_factor)) for x, y, w, h in faces_grouped]
            else:
                faces = list(faces_grouped)

        best_focus_x = frame_width // 2
        best_focus_y = frame_height // 2
        best_confidence = 0.0

        if len(faces) > 0:
            # Track faces dan assign IDs
            faces_with_ids = face_tracker.update_faces(list(faces))
            
            # Deteksi speaker dalam faces
            speaker_focus, speaker_score, current_speaker_id = _detect_speaker_face(
                frame, prev_frame_gray, faces_with_ids,
                face_cascade, eye_cascade, mouth_cascade,
                active_speaker_id=active_speaker_id,
                last_valid_focus_x=last_valid_focus_x,
                last_valid_focus_y=last_valid_focus_y
            )
            
            if current_speaker_id != -1:
                active_speaker_id = current_speaker_id
            
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
            if last_valid_focus_x is not None:
                # Pertahankan posisi wajah terakhir jika cascade sesaat kehilangan wajah
                best_focus_x = last_valid_focus_x
                best_focus_y = last_valid_focus_y
                best_confidence = 0.5
            else:
                object_center = _detect_prominent_region(frame, frame_area)
                if object_center is not None:
                    best_focus_x, best_focus_y = object_center
                    best_confidence = 0.75
        else:
            # Simpan posisi wajah yang valid
            last_valid_focus_x = best_focus_x
            last_valid_focus_y = best_focus_y

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


