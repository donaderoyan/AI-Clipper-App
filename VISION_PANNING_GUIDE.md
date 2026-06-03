# Smart Panning Improvements - Documentation

## 🎯 Overview

Smart panning dalam `vision.py` kini menghasilkan path crop dinamis untuk setiap frame atau interval kecil klip dengan fitur **Multi-Speaker Detection**:
1. **Deteksi Mata** - Mendeteksi mata dalam wajah untuk fokus yang lebih presisi
2. **Mouth Activity Detection** - Mendeteksi pergerakan bibir untuk identifikasi speaker
3. **Optical Flow Analysis** - Menganalisis pergerakan dalam wajah untuk deteksi aktivitas
4. **Speaker Scoring** - Menentukan orang yang sedang berbicara dalam multi-speaker scenarios
5. **Face Tracking** - Melacak identitas face sepanjang waktu untuk konsistensi
6. **Per-Frame Tracking** - Mengumpulkan posisi fokus dari setiap frame yang dianalisis
7. **Trajectory Smoothing** - Mengurangi jitter dengan moving average filter
8. **Dynamic Crop Path** - Menghasilkan tuple `(frame_index, crop_x, crop_y)` untuk panning FFmpeg

---

## 🔄 Alur Kerja

### 1. **Face & Profile Detection** (Haar Cascade)
```
Video Frame → Grayscale 
            → haarcascade_frontalface_default.xml (Wajah Lurus)
            → haarcascade_profileface.xml (Menyamping Kiri & Kanan)
            → cv2.groupRectangles (Mencegah deteksi ganda)
```
Mendeteksi seluruh wajah (baik menghadap kamera maupun menyamping) dalam satu frame.

### 2. **Eye Detection** (Validasi Tambahan)
```
Face ROI → haarcascade_eye.xml → Detect Eyes
```
Digunakan hanya sebagai bonus skor (membantu membedakan wajah dari corak dinding).

### 3. **Net Optical Flow** (Deteksi Bicara Akurat)
```
Prev Frame vs Current Frame 
   → Flow Mulut (Pergerakan Bibir)
   → Flow Kepala (Pergerakan Dahi/Mata)
   → Net Mouth Flow = max(0, Flow Mulut - Flow Kepala)
```
Menyaring pergerakan mengangguk/menggeleng, dan secara presisi menangkap aktivitas rahang/bibir yang terbuka-tertutup.

### 4. **Speaker Scoring & Spatial Hysteresis**
```
Priority Weighting:
├─ Net Mouth Flow        → 3.0 weight (Indikator UTAMA Berbicara)
├─ Face Motion           → 0.5 weight (Indikator aktivitas)
├─ Eye Detection         → 0.2 weight (Validasi wajah)
├─ Static Penalty        → -2.0 (Menghukum objek mati/dinding)
└─ Spatial Hysteresis    → +2.5 (Menahan fokus kamera di lokasi yang sama)

Total Score = Speaking_Score + Eye_Score - Penalty + Hysteresis
```
Face dengan score tertinggi dipilih sebagai pembicara aktif.

### 6. **Confidence Scoring**
```
Speaker Detection Result:
├─ Both Eyes Found + High Mouth Activity     → Confidence = 2.0+ (Optimal)
├─ Eyes Found + Moderate Mouth Activity      → Confidence = 1.5-2.0 (Good)
└─ Eyes Found Only / No Eyes                 → Confidence = 0.5-1.5 (Fallback)
```

### 7. **Trajectory Smoothing**
```
Raw Focus Points → Moving Average Filter (5-frame window)
                → Smoothed Focus Points → Crop Coordinates
```
Mengurangi jitter gerakan kamera dengan smoothing.

### 8. **Dynamic Crop Path**
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
| **Mouth Detection** | ❌ Tidak ada | ✅ Deteksi mulut & aktivitas per-frame |
| **Optical Flow** | ❌ Tidak ada | ✅ Motion analysis untuk setiap face |
| **Multi-Speaker Support** | ❌ Hanya 1 speaker | ✅ Prioritas speaker aktif |
| **Face Tracking** | ❌ Tidak ada | ✅ Track ID untuk temporal consistency |
| **Focus Point** | Rata-rata semua wajah | Per-frame dengan speaker priority |
| **Smoothing** | ❌ Tidak ada | ✅ Moving average (5 frames) |
| **Output** | Satu crop coordinate | ✅ Path crop dinamis |

---

## 🧠 Speaker Detection Algorithm

### Input Analysis Per-Face:

1. **Net Mouth Flow** (0.0-2.0)
   - Selisih gerak mulut dan gerak kepala.
   - 0.0: Mulut tertutup rapat atau mengangguk.
   - 2.0: Mulut terbuka lebar dan berbicara aktif.

2. **Static Penalty** (-2.0 atau 0.0)
   - Menangkal *False Positive* Haar Cascade (wajah palsu di dinding/poster).
   - Objek dengan pergerakan murni `0.0` akan dihukum berat dan diabaikan.

3. **Spatial Hysteresis** (+2.5 atau 0.0)
   - Mengingat posisi target terakhir (`last_valid_focus`). 
   - Jika wajah saat ini berjarak < 150px dari posisi terakhir, kamera mengunci padanya (mencegah kamera mudah berpindah ke orang lain).

### Speaker Selection Logic:

```python
# For each detected face:
speaking_score = (mouth_score * 3.0) + (flow_score * 0.5)
total_score = speaking_score + (eye_score * 0.2) - static_penalty + hysteresis_bonus

# Select face dengan highest total_score sebagai speaker
selected_speaker = max(faces, key=lambda f: f['total_score'])
```

**Keuntungan:**
- ✅ Fokus absolut pada aktivitas bicara (mengabaikan orang yang sekadar bergerak).
- ✅ Mengalahkan *False Positives* dari background.
- ✅ *Tracking* fisik yang anti-kedip/anti-amnesia.

---

## 🛠️ Cara Menggunakan

### Di Backend Pipeline
```python
from pathlib import Path
from app.services.vision import calculate_crop_path
from app.services.renderer import render_clip

# Hitung crop path untuk klip (sekarang dengan speaker detection)
target_w, target_h, crop_positions = calculate_crop_path(
    video_path=Path("/app/data/raw/abc123/video.mp4"),
    aspect_ratio="9:16",
    start=10.0,
    end=40.0,
)

# Render klip dengan dynamic panning (mengikuti speaker)
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
- Hasilnya: panning mengikuti speaker aktif sepanjang clip

### Testing
```bash
# Test dengan video multi-speaker
docker compose exec -T backend python test_vision.py \
    /app/data/raw/abc123/video.mp4 9:16 0 30

# Lihat hasil dalam output/abc123/
```

---

## 🔧 Customization & Tuning

### Speaker Scoring Weights
Jika hasil tidak optimal, sesuaikan weights dalam `_detect_speaker_face()`:
```python
# Current weights:
total_score = (eye_score * 0.4) + (mouth_score * 0.4) + (flow_score * 0.2)

# Example: Prioritas mouth activity lebih tinggi
# total_score = (eye_score * 0.2) + (mouth_score * 0.7) + (flow_score * 0.1)
```

### Face Tracking Distance Threshold
Jika face tracking terlalu sensitif atau terlalu lemah:
```python
face_tracker = FaceTracker(max_distance_threshold=100.0)  # Default
# Naikan untuk lebih toleran terhadap pergerakan besar
# Turunkan untuk lebih ketat dalam tracking
```

### Mouth Detection Parameters
Jika mouth detection tidak akurat:
```python
mouths = mouth_cascade.detectMultiScale(
    mouth_roi,
    scaleFactor=1.1,    # Naikan untuk deteksi lebih agresif
    minNeighbors=4,     # Turunkan untuk lebih sensitif
    minSize=(15, 10),   # Sesuaikan dengan ukuran mulut dalam video
)
```

---

## 📈 Performance Notes

- **Computational Cost**: Speaker detection menambah ~15-20% CPU usage dibanding single-speaker
- **Frame Processing**: Setiap frame dianalisis (3-5ms per frame pada CPU standar)
- **Memory Usage**: Face tracking menyimpan history untuk last 5 frames per face

---

## 📈 Parameter Konfigurasi

### Dalam `_smooth_trajectory()`
```python
alpha: float = 0.1  # Faktor EMA (Exponential Moving Average)
snap_threshold = 150.0  # Jarak (pixel) untuk Instant Cut
```
- **EMA Tracking**: Mengikuti orang yang bergerak/berjalan dengan mulus tanpa guncangan kamera.
- **Snap Threshold**: Jika target berpindah jauh secara instan (ganti pembicara), kamera memicu *Cut* 0-detik.

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

