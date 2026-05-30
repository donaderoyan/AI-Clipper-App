# Smart Panning Improvements - Documentation

## 🎯 Overview

Smart panning dalam `vision.py` kini menghasilkan path crop dinamis untuk setiap frame atau interval kecil klip:
1. **Deteksi Mata** - Mendeteksi mata dalam wajah untuk fokus yang lebih presisi
2. **Per-Frame Tracking** - Mengumpulkan posisi fokus dari setiap frame yang dianalisis
3. **Trajectory Smoothing** - Mengurangi jitter dengan moving average filter
4. **Dynamic Crop Path** - Menghasilkan tuple `(frame_index, crop_x, crop_y)` untuk panning FFmpeg

---

## 🔄 Alur Kerja

### 1. **Face Detection** (Haar Cascade)
```
Video Frame → Grayscale → haarcascade_frontalface_default.xml
```
Mendeteksi wajah dalam frame menggunakan Haar Cascade classifier.

### 2. **Eye Detection** (Prioritas Tinggi)
```
Face ROI → haarcascade_eye.xml → Detect Eyes
```
Jika mata terdeteksi dalam wajah, gunakan posisi mata sebagai focus point.

### 3. **Confidence Scoring**
```
Priority:
├─ Both Eyes Found       → Confidence = 2.0 (Gunakan rata-rata posisi mata)
├─ One Eye Found         → Confidence = 1.5 (Gunakan posisi mata)
└─ No Eyes Found         → Confidence = 1.0 (Gunakan pusat wajah)
```

### 4. **Trajectory Smoothing**
```
Raw Focus Points → Moving Average Filter (5-frame window)
→ Smoothed Focus Points → Crop Coordinates
```
Mengurangi jitter gerakan kamera dengan smoothing.

### 5. **Dynamic Crop Path**
```
Smoothed Points → [(frame_idx, crop_x, crop_y), ...]
→ FFmpeg expression for x and y
```
Menghasilkan path dinamis untuk panning sepanjang clip.

---

## 📊 Perbedaan Implementasi

| Aspek | Sebelum | Saat ini |
|-------|---------|---------|
| **Frame Analysis** | 10 frames sampel | Semua frame dalam range yang dianalisis |
| **Eye Detection** | ❌ Tidak ada | ✅ Deteksi mata per-frame |
| **Focus Point** | Rata-rata semua wajah | Per-frame dengan prioritas mata/objek |
| **Smoothing** | ❌ Tidak ada | ✅ Moving average (5 frames) |
| **Output** | Satu crop coordinate | ✅ Path crop dinamis |

---

## 🛠️ Cara Menggunakan

### Di Backend Pipeline
```python
from pathlib import Path
from app.services.vision import calculate_crop_path
from app.services.renderer import render_clip

# Hitung crop path untuk klip
target_w, target_h, crop_positions = calculate_crop_path(
    video_path=Path("/app/data/raw/abc123/video.mp4"),
    aspect_ratio="9:16",
    start=10.0,
    end=40.0,
)

# Render klip dengan dynamic panning
render_clip(
    video_path=Path("/app/data/raw/abc123/video.mp4"),
    output_path=Path("/app/data/output/abc123/clip.mp4"),
    start=10.0,
    end=40.0,
    crop_params=(target_w, target_h, crop_positions),
)
```

### Output yang dihasilkan
- `crop_positions` menghasilkan tuple: `(frame_index, crop_x, crop_y)`
- `renderer.py` membangun ekspresi FFmpeg `x`/`y`
- Hasilnya: panning mengikuti fokus temporal sepanjang clip

### Testing
```bash
docker compose exec -T backend python test_vision.py \
    /app/data/raw/abc123/video.mp4 9:16 0 30
```

---

## 📈 Parameter Konfigurasi

### Dalam `_smooth_trajectory()`
```python
window_size: int = 5  # Ukuran moving average window
```
- **Lebih kecil (3)**: Lebih responsif tapi jittery
- **Standard (5)**: Balanced smoothing
- **Lebih besar (7-9)**: Lebih smooth tapi less responsive

### Dalam `face_cascade.detectMultiScale()`
```python
scaleFactor=1.1          # Pyramid scaling (1.05 = lebih sensitif)
minNeighbors=5           # Minimum neighbors untuk accept detection
minSize=(30, 30)         # Minimum face size
```

### Dalam `eye_cascade.detectMultiScale()`
```python
scaleFactor=1.05         # Smaller pyramid scale untuk mata
minNeighbors=5           # Neighbors requirement
minSize=(15, 15)         # Minimum eye size
```

---

## 🐛 Troubleshooting

### Panning Masih Jittery
**Solusi:**
- Naikkan `window_size` di `_smooth_trajectory()` dari 5 ke 7
- Naikkan `minNeighbors` di `face_cascade.detectMultiScale()` dari 5 ke 7

### Mata Tidak Terdeteksi
**Solusi:**
- Pastikan video quality cukup bagus (minimal 480p)
- Ubah `scaleFactor` eye detection dari 1.05 ke 1.03 (lebih sensitif)
- Turunkan `minSize` eye detection dari (15, 15) ke (10, 10)

### Crop Tidak Bergerak / Selalu Terpusat
**Penyebab:** `calculate_crop_path()` fallback ke center karena tidak ada fokus valid di interval
**Solusi:**
- Pastikan ada wajah/objek penting dalam range waktu tersebut
- Cek log dan status deteksi pada `docker compose logs backend`

---

## 🚀 Future Enhancements

### 1. **Optical Flow Tracking** (Priority: Medium)
```python
# Menggunakan Lucas-Kanade optical flow untuk tracking yang lebih stabil
cv2.calcOpticalFlowPyrLK(...)
```

### 2. **Head Pose / Landmark Compensation** (Priority: Medium)
```python
# Deteksi landmark untuk adjust crop berdasarkan head pose
# Menggunakan dlib atau MediaPipe
```

### 3. **Multi-Person Focus** (Priority: Low)
```python
# Jika beberapa orang terdeteksi, pilih fokus terbaik atau apply smart selection
```

### 4. **Caching Cascade Classifiers**
- Saat ini classifier di-load per pemanggilan
- Pertimbangkan caching agar performance lebih konsisten

---

## 📝 Notes

- `vision.py` sekarang mengembalikan crop path dinamis
- `renderer.py` menggunakan ekspresi FFmpeg untuk interpolasi X/Y
- Input crop path adalah list `(frame_index, crop_x, crop_y)`
- Path ini memberi efek panning yang lebih smooth dibanding crop statis

