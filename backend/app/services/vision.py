import cv2
import math
from pathlib import Path
from typing import Tuple

def calculate_crop(video_path: Path, aspect_ratio: str, start: float = 0.0, end: float = 0.0) -> Tuple[int, int, int, int]:
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
        target_height = min(height, int(width * 16 / 9)) # Usually height is determined by width in 16:9 from vertical
        target_width = width
        if target_height > height:
           target_height = height
           target_width = int(height * 16 / 9)
    else:
        capture.release()
        return width, height, 0, 0

    if start > 0:
        capture.set(cv2.CAP_PROP_POS_MSEC, start * 1000)

    # Initialize Haar Cascade for face detection
    # Using default OpenCV haar cascades path.
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    total_frames_to_check = 10 # Sample 10 frames across the clip duration
    duration = max(end - start, 1.0)
    step_sec = duration / total_frames_to_check
    
    faces_centers = []
    
    for i in range(total_frames_to_check):
        t = start + (i * step_sec)
        capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = capture.read()
        if not ret:
            break
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Try face detection first
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        if len(faces) > 0:
            for (x, y, w, h) in faces:
                faces_centers.append((x + w//2, y + h//2))
        else:
            # Fallback to person detection if no face found
            boxes, weights = hog.detectMultiScale(frame, winStride=(8, 8))
            if len(boxes) > 0:
                for (x, y, w, h) in boxes:
                    faces_centers.append((x + w//2, y + h//2))

    capture.release()

    # Determine focal point
    if faces_centers:
        # Calculate average center of subjects
        avg_x = sum(c[0] for c in faces_centers) // len(faces_centers)
        avg_y = sum(c[1] for c in faces_centers) // len(faces_centers)
    else:
        # Default to center if nothing is found
        avg_x = width // 2
        avg_y = height // 2

    # Calculate crop coordinates based on focal point and target dimensions
    crop_x = avg_x - (target_width // 2)
    crop_y = avg_y - (target_height // 2)

    # Ensure crop window stays within video bounds
    crop_x = max(0, min(crop_x, width - target_width))
    crop_y = max(0, min(crop_y, height - target_height))

    return target_width, target_height, crop_x, crop_y

