# Speaker Detection Implementation Guide

## 📋 Overview

Modul speaker detection dalam `vision.py` menyediakan kemampuan untuk mendeteksi dan melacak orang yang **sedang berbicara** dalam video dengan multiple people. Fitur ini dirancang untuk mengatasi limitation sistem sebelumnya yang hanya bisa menangani single-speaker scenario dengan baik.

---

## 🏗️ Architecture

### Core Components

```
Vision Analysis Pipeline
│
├─ Face & Profile Detection (Haar Cascade)
│  └─ Detect all faces (frontal, kiri, kanan) dan grouping
│
├─ Net Optical Flow Computation
│  ├─ Hitung flow mulut (bawah wajah)
│  ├─ Hitung flow kepala (atas wajah)
│  └─ Net Mouth Flow = max(0, mulut - kepala)
│
├─ Speaker Detection (per-face analysis)
│  ├─ Eye Detection → eye_score (0.0-2.0)
│  ├─ Net Mouth Flow → speaking_score
│  └─ Static Detection → penalty_score
│
├─ Speaker Selection (weighted scoring + Hysteresis)
│  └─ total_score = (mouth*3.0) + (flow*0.5) + (eye*0.2) - penalty + hysteresis
│
└─ Focus Point Generation
   ├─ Trajectory Smoothing (EMA)
   └─ Keyframe Protection & FFmpeg Crop
```

---

## 🔍 Module Functions

### 1. `FaceTracker` Class

**Purpose**: Track face identity across frames

```python
class FaceTracker:
    def __init__(self, max_distance_threshold: float = 100.0)
    def update_faces(self, faces: List[Tuple[int, int, int, int]]) -> List[Tuple[int, Tuple[int, int, int, int]]]
```

**Parameters**:
- `max_distance_threshold`: Maximum pixel distance untuk mencocokkan detection dengan previous frame
  - Default: 100.0 pixels
  - Increase: Lebih toleran terhadap pergerakan besar
  - Decrease: Lebih ketat dalam matching, hindari false matches

**Algorithm**:
1. Hitung center point dari setiap detected face
2. Match dengan existing face IDs menggunakan Euclidean distance
3. Assign new ID untuk faces yang tidak match (new faces)
4. Cleanup IDs yang sudah tidak terdeteksi

**Usage**:
```python
tracker = FaceTracker(max_distance_threshold=100.0)
faces_with_ids = tracker.update_faces([(x, y, w, h), ...])
# Returns: [(face_id, (x, y, w, h)), ...]
```

---

### 2. `_detect_mouth_activity()`

**Purpose**: Menghitung Net Optical Flow (Pergerakan Mulut Bersih)

```python
def _detect_mouth_activity(
    prev_frame: np.ndarray,
    curr_frame: np.ndarray,
    face_box: Tuple[int, int, int, int],
    mouth_cascade,  # Legacy parameter (not used for detection, only for fallback)
) -> float
```

**Algorithm**:
1. Membagi wajah menjadi bagian atas (mata/dahi) dan bagian bawah (mulut/rahang).
2. Menghitung Optical Flow pada bagian bawah (Mulut).
3. Menghitung Optical Flow pada bagian atas (Kepala).
4. `Net Mouth Flow = max(0, Flow_Mulut - Flow_Kepala)`.

**Why Net Optical Flow?**
- Jika orang hanya mengangguk/menggeleng, seluruh wajah bergerak, sehingga `Net Flow` menjadi 0.
- Jika orang berbicara, rahang/mulut bergerak ekstra dibanding dahi, menghasilkan `Net Flow` > 0.
- Ini 100x lebih akurat daripada menggunakan Haar Cascade mulut yang sering berhalusinasi atau salah deteksi gigi.

---

### 3. `_calculate_optical_flow_magnitude()`

**Purpose**: Detect motion dalam face region

```python
def _calculate_optical_flow_magnitude(
    prev_frame: np.ndarray,
    curr_frame: np.ndarray,
    roi: Tuple[int, int, int, int],
) -> float
```

**Parameters**:
- `prev_frame`: Grayscale frame sebelumnya
- `curr_frame`: Grayscale frame saat ini
- `roi`: Region of interest (x, y, w, h)

**Return Value**: Float (0.0 - 1.0)
- 0.0: No motion
- 0.5: Moderate motion (non-speech movement)
- 1.0: High motion (speech-related movement)

**Algorithm**:
1. Extract ROI dari kedua frame
2. Calculate dense optical flow menggunakan Farneback algorithm
3. Compute magnitude = sqrt(flow_x^2 + flow_y^2)
4. Return average magnitude (normalized)

**Why Farneback?**
- Robust untuk facial motion
- Works well pada lower resolutions
- Computationally efficient
- Good untuk detecting lip/jaw movement

---

### 4. `_detect_speaker_face()`

**Purpose**: Identify speaker (face yang sedang berbicara)

```python
def _detect_speaker_face(
    frame: np.ndarray,
    prev_frame: Optional[np.ndarray],
    faces_with_ids: List[Tuple[int, Tuple[int, int, int, int]]],
    face_cascade,
    eye_cascade,
    mouth_cascade,
) -> Tuple[Optional[Tuple[int, int]], float]
```

**Parameters**:
- `frame`: Current frame (BGR)
- `prev_frame`: Previous frame grayscale (untuk optical flow)
- `faces_with_ids`: [(face_id, (x, y, w, h)), ...]
- Cascades: Haar Cascade classifiers

**Return Value**: Tuple (focus_point, confidence)
- `focus_point`: (x, y) position untuk crop center, atau None
- `confidence`: Score dari detected speaker (0.0-2.0+)

**Scoring Algorithm**:

```python
# For each face:
eye_score = detect_eyes(face_roi)           # 0.0-2.0
mouth_score = _detect_mouth_activity(...)   # Net Mouth Flow (0.0-2.0)
flow_score = _calculate_optical_flow_magnitude(...) * 1.5  # 0.0-2.0

speaking_score = (mouth_score * 3.0) + (flow_score * 0.5)
static_penalty = 2.0 if (flow_score < 0.05 and mouth_score < 0.05) else 0.0
hysteresis = 2.5 if (distance_to_last_valid_focus < 150px) else 0.0

total_score = speaking_score + (eye_score * 0.2) - static_penalty + hysteresis

# Select face dengan highest score
best_speaker = max(faces_with_ids, key=lambda f: f['total_score'])
```

**Weight Justification**:
- **Mouth Score (3.0)**: Indikator absolut dari aktivitas berbicara (Net Mouth Flow).
- **Hysteresis (2.5)**: Mencegah kamera berpindah hanya karena AI sesaat berkedip.
- **Static Penalty (-2.0)**: Menghukum keras deteksi wajah palsu (dinding/poster) yang pergerakannya 0.0.
- **Eye Score (0.2)**: Hanya sebagai validasi bahwa itu benar-benar wajah manusia.

---

### 5. `_analyze_frames_with_speaker_detection()`

**Purpose**: Main analysis function dengan speaker detection integration

```python
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
) -> List[Tuple[int, int, int]]
```

**Return Value**: List of (frame_index, crop_x, crop_y)

**Processing Steps**:
1. Iterate through video frames (dengan frame sampling)
2. For each frame:
   - Detect faces
   - Track face IDs
   - Detect speaker (menggunakan `_detect_speaker_face()`)
   - Calculate crop position untuk speaker
3. Smooth trajectory dengan moving average
4. Convert focus points ke crop coordinates

---

## 📊 Data Flow

### Single Frame Processing

```
Frame (BGR)
    ↓
Convert to Grayscale
    ↓
Face Detection (Haar Cascade)
    ↓
Face Tracking (FaceTracker)
    ├─ face_id_1: (x1, y1, w1, h1)
    ├─ face_id_2: (x2, y2, w2, h2)
    └─ face_id_3: (x3, y3, w3, h3)
    ↓
For Each Face:
    ├─ Extract face_roi
    ├─ Eye Detection → eye_score
    ├─ Mouth Detection → mouth_score
    ├─ Optical Flow → flow_score
    └─ Calculate total_score
    ↓
Select Speaker (highest total_score)
    ↓
Extract Focus Point
    ├─ From eye centers jika mata terdeteksi
    └─ Dari face center jika tidak
    ↓
Append (frame_idx, focus_x, focus_y)
```

### Multiple Frame Processing

```
Frame Sequence [f1, f2, f3, ..., fn]
    ↓
Per-Frame Processing (see above)
    ↓
Raw Focus Points [(0, x0, y0), (1, x1, y1), ...]
    ↓
Trajectory Smoothing (Moving Average, window=5)
    ↓
Smoothed Focus Points [(0, x0', y0'), (1, x1', y1'), ...]
    ↓
Crop Coordinate Generation
    └─ crop_x = focus_x - (target_width / 2)
    └─ crop_y = focus_y - (target_height / 2)
    ↓
Final Output [(0, crop_x0, crop_y0), (1, crop_x1, crop_y1), ...]
```

---

## 🎯 Multi-Speaker Scenario Example

```
Frame dengan 3 orang:
┌─────────────────────────────┐
│  Person A (speaking)  │ B   │
│  Mouth: open (score 1.8)    │
│  Eyes: detected (score 2.0) │
│  Motion: high (score 1.8)   │
│  Total: (2.0*0.4)+(1.8*0.4)+(1.8*0.2) = 1.88 ← SELECTED
│                             │
│  Person B (listening)│      │
│  Mouth: closed (score 0.3)  │
│  Eyes: detected (score 1.8) │
│  Motion: low (score 0.2)    │
│  Total: (1.8*0.4)+(0.3*0.4)+(0.2*0.2) = 0.86
│                    │ C      │
│  Person C (background)      │
│  Mouth: not detected (score 0)
│  Eyes: not detected (score 0.5)
│  Motion: low (score 0.1)    │
│  Total: (0.5*0.4)+(0*0.4)+(0.1*0.2) = 0.22
└─────────────────────────────┘

Result: Pan ke Person A (speaker dengan score tertinggi)
```

---

## ⚙️ Configuration & Tuning

### 1. Speaker Scoring Weights

**Current (Balanced)**:
```python
total_score = (eye_score * 0.4) + (mouth_score * 0.4) + (flow_score * 0.2)
```

**If mouth detection underperforms**:
```python
# Increase mouth weight, decrease eye weight
total_score = (eye_score * 0.2) + (mouth_score * 0.6) + (flow_score * 0.2)
```

**If optical flow too noisy**:
```python
# Reduce flow weight, increase eye + mouth
total_score = (eye_score * 0.45) + (mouth_score * 0.45) + (flow_score * 0.1)
```

---

### 2. Face Tracking Threshold

```python
# More tolerant (untuk speaker bergerak cepat)
face_tracker = FaceTracker(max_distance_threshold=150.0)

# More strict (untuk video dengan banyak orang berdekatan)
face_tracker = FaceTracker(max_distance_threshold=50.0)
```

---

### 3. Mouth Detection Parameters

```python
# Current
mouths = mouth_cascade.detectMultiScale(
    mouth_roi,
    scaleFactor=1.1,    # Pyramid scale
    minNeighbors=4,     # Strictness
    minSize=(15, 10),   # Minimum size
    maxSize=(int(fw * 0.6), int(fh * 0.3)),  # Maximum size
)

# For high-resolution videos (1080p+)
mouths = mouth_cascade.detectMultiScale(
    mouth_roi,
    scaleFactor=1.05,   # More careful scaling
    minNeighbors=5,     # More strict
    minSize=(20, 15),   # Larger minimum
    maxSize=(int(fw * 0.5), int(fh * 0.25)),
)

# For low-resolution videos (480p or less)
mouths = mouth_cascade.detectMultiScale(
    mouth_roi,
    scaleFactor=1.2,    # More aggressive
    minNeighbors=3,     # More lenient
    minSize=(10, 8),    # Smaller minimum
    maxSize=(int(fw * 0.7), int(fh * 0.4)),
)
```

---

### 4. Optical Flow Parameters

```python
# Current (moderate motion sensitivity)
flow = cv2.calcOpticalFlowFarneback(
    roi_prev, roi_curr,
    None,
    pyr_scale=0.5,      # Pyramid scale (0.5 = standard)
    levels=3,           # Levels (3 = standard)
    winsize=15,         # Window size (15 = standard)
    iterations=3,       # Iterations
    poly_n=5,           # Polynomial neighbor
    poly_sigma=1.2,     # Polynomial sigma
    flags=0
)

# For more robust detection (lebih toleran terhadap noise)
flow = cv2.calcOpticalFlowFarneback(
    roi_prev, roi_curr,
    None,
    pyr_scale=0.5,
    levels=4,           # More levels
    winsize=20,         # Larger window
    iterations=5,       # More iterations
    poly_n=7,
    poly_sigma=1.5,
    flags=0
)
```

---

## 🧪 Testing & Validation

### Test Cases

**Case 1: Single Speaker**
```
Video: Documentary dengan 1 orang berbicara sepanjang durasi
Expected: Pan mengikuti speaker konsisten
Validation: Crop coordinates should be stable pada speaker's face
```

**Case 2: Two Speakers (Dialog)**
```
Video: Interview dengan 2 orang berganti berbicara
Expected: Pan switch antara speakers saat mereka berbicara
Validation: Crop coordinates should transition smoothly ke speaker aktif
```

**Case 3: Multiple Speakers (Group)**
```
Video: Panel discussion dengan 3-4 orang
Expected: Pan fokus ke orang yang sedang berbicara
Validation: Mouth activity scores should reflect aktual speakers
```

**Case 4: Low Lighting**
```
Video: Poorly lit scene
Expected: Graceful degradation (fall back ke eye detection)
Validation: System should still work, mungkin less accurate but functional
```

---

### Debug Metrics

Untuk debugging, print intermediate scores:

```python
def _detect_speaker_face(...):
    # ... [existing code] ...
    
    for face_id, (fx, fy, fw, fh) in faces_with_ids:
        # ... calculate scores ...
        
        # Debug output
        print(f"Face {face_id}: eye={eye_score:.2f}, mouth={mouth_score:.2f}, flow={flow_score:.2f}, total={total_score:.2f}")
    
    return speaker_focus, highest_score
```

---

## 🚀 Performance Optimization

### Computation Cost Breakdown
- Face Detection: ~2ms per frame
- Eye Detection: ~1ms per face
- Mouth Detection: ~2ms per face
- Optical Flow: ~3-5ms per face
- **Total: ~8-15ms per frame** (on CPU)

### Optimization Tips

1. **Reduce Frame Sampling**
   ```python
   # Current: process every frame (or fewer with frame_step)
   # Option: increase frame_step untuk faster processing
   frame_step = max(1, (end_frame - start_frame) // 60)  # Process 60 frames max
   ```

2. **Simplify Cascades**
   ```python
   # Use alternative smaller cascades jika available
   # atau reduce cascade parameters (minNeighbors, scales)
   ```

3. **Disable Optical Flow untuk Fast Mode**
   ```python
   # Set flow_score = 0 jika tidak diperlukan
   flow_score = 0.0  # or detect only if mouth_score low
   ```

4. **Parallel Processing**
   ```python
   # Future: Process multiple faces in parallel
   # Current: Sequential per-face processing
   ```

---

## 🔗 Integration Points

### In `vision.py`:
- `calculate_crop()` - Uses `_analyze_frames_with_speaker_detection()`
- `calculate_crop_path()` - Uses `_analyze_frames_with_speaker_detection()`

### In `pipeline.py`:
- `run_ai_pipeline()` - Calls `calculate_crop_path()` untuk setiap clip
- Results digunakan dalam `render_clip()` untuk dynamic panning

### In `renderer.py`:
- Receives crop_positions tuple list
- Generates FFmpeg `-vf` expression untuk panning

---

## 📋 Future Improvements

1. **Advanced Speaker Recognition**
   - Use face embeddings (e.g., FaceNet) untuk identify speakers
   - Dapat mendeteksi jika same person berbicara di multiple locations

2. **Audio-Visual Synchronization**
   - Use audio features (pitch, energy) sebagai additional scoring input
   - Combine dengan mouth activity untuk more accurate detection

3. **Head Pose Estimation**
   - Detect jika speaker menghadap kamera (more confident detection)
   - Fallback jika speaker profile/turned away

4. **Deep Learning Based**
   - Replace Haar Cascade dengan YOLO atau SSD untuk face detection
   - Use CNN untuk mouth/lip activity detection
   - Potentially faster dan lebih akurat

5. **Temporal Model**
   - Use Kalman Filter atau HMM untuk smooth speaker transitions
   - Predict speaker sebelum visible mouth movement

---

## 📚 References

- OpenCV Cascade Classifiers: https://docs.opencv.org/master/db/d28/tutorial_cascade_classifier.html
- Optical Flow (Farneback): https://docs.opencv.org/master/d7/d8b/tutorial_py_lucas_kanade.html
- Face Detection Haar Cascades: https://github.com/opencv/opencv/tree/master/data/haarcascades

---
