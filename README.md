# AI Video Clipper

<div style="display: flex; align-items: center; justify-content: space-between; padding: 16px; background-color: #f9ad2aff; border-radius: 20px; gap: 24px; flex-wrap: wrap;">
  <div style="flex: 1 1 320px; min-width: 260px; color: #1a1a1a;">
    <strong style="font-size: 1.05rem;">Terima kasih banyak untuk siapa pun yang ingin traktir kopi — dukunganmu sangat berarti dan membantu proyek ini terus berkembang! ☕</strong>
    <p style="margin: 12px 0 0 0; font-size: 0.98rem; color: #222;">Scan kode QR atau klik badge untuk mengirim kopi.</p>
  </div>
</div>

[![Dukung di Saweria -- https://saweria.co/odonnnn](https://img.shields.io/badge/Dukung%20Saya-Saweria-orange)](https://saweria.co/odonnnn)

> Ini adalah Web App untuk memotong video panjang menjadi video pendek vertikal (9:16) atau horizontal (16:9) secara otomatis menggunakan AI lokal. Aplikasi ini menggunakan arsitektur Local Microservice: Electron (Frontend) dan FastAPI Python (Backend).

## Deskripsi Aplikasi

**AI Video Clipper** adalah solusi end-to-end untuk mengubah konten video dokumenter panjang menjadi klip video pendek yang viral-ready. Aplikasi ini menggunakan:

- **Local AI** untuk analisis konten tanpa mengirim data ke cloud
- **Smart Content Detection** untuk menemukan momen puncak narasi
- **Automated Cropping & Panning** untuk mengoptimalkan framing video
- **Dynamic Subtitles** untuk meningkatkan engagement

## Fokus Aplikasi

Aplikasi ini dirancang khusus untuk memproses:

1. **Penceritaan Bergaya Dokumenter** - Video dengan narasi yang kaya konteks
2. **Deteksi Momen Puncak** - Insiden historis, fakta tragis/unik, atau hook yang kuat
3. **Pemotongan Otomatis** - Ekstrak segmen terbaik tanpa editing manual
4. **Optimasi untuk Platform Sosial** - Format vertical (9:16) untuk TikTok/Reels atau horizontal (16:9) untuk YouTube Shorts

## Contoh Use Case

- Ubah dokumenter 1 jam menjadi 30+ klip 15 detik untuk TikTok
- Ekstrak momen menarik dari podcast video secara otomatis
- Buat konten short-form dari webinar atau kuliah panjang

## Tech Stack

- **Frontend:** Electron, TypeScript, React, Tailwind CSS
- **Backend:** Python 3.10+, FastAPI, Docker
- **AI & Media:** yt-dlp, faster-whisper, Ollama (Local LLM), OpenCV, FFmpeg

---

## Prerequisites
- **Docker Desktop** terinstall dan berjalan (WSL2 direkomendasikan di Windows)
- **Ollama** running di Docker (untuk Local LLM)
- **Node.js** hanya diperlukan jika Anda ingin menjalankan frontend secara lokal tanpa Docker

## Quick Start (Docker-first)

Semua service frontend dan backend bisa dijalankan sepenuhnya di Docker. Ini membantu menghindari masalah dependensi lokal seperti `cv2` atau `ffmpeg`.

1. Build dan jalankan semua service dengan Docker Compose:

```bash
docker-compose up --build
```

2. Buka aplikasi frontend di browser:

```text
http://localhost:5173
```

Backend akan tersedia di:

```text
http://localhost:8000
```

3. Hentikan service dengan:

```bash
docker-compose down
```

### Optional: Jalankan frontend secara lokal

Jika Anda ingin tetap menjalankan frontend tanpa Docker, gunakan opsi ini:

```bash
cd frontend
npm install
npm run dev
```

Namun jika tujuan Anda adalah memindahkan seluruh ekosistem ke Docker, langkah ini tidak diperlukan.

---

### Frontend (Sama untuk Kedua Option)


Di terminal baru (TIDAK di dalam container jika pakai Dev Container):

```bash
# Masuk folder frontend
cd frontend

# Install dependencies
npm install

# Jalankan development server
npm run dev
```

Frontend akan berjalan di `http://localhost:5173` (atau port lain yang ditampilkan)

---
## API Testing

### Test Unduh & Proses Video YouTube

```bash
curl --location 'http://localhost:8000/api/v1/process' \
  --header 'Content-Type: application/json' \
  --data '{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "aspect_ratio": "9:16",
    "prompt_context": "Cari momen yang menarik dan absurd"
  }'
```

### Check Status Job

```bash
curl 'http://localhost:8000/api/v1/status/{job_id}'
```

## File Structure

```
/ai-clipper-app
├── frontend/              # Electron + React + TypeScript
├── backend/               # FastAPI + Python (Docker)
├── data/                  # Shared volume untuk raw, temp, output
├── docker-compose.yml     # Orkestrasi Docker
├── README.md              # File ini
├── VISION_PANNING_GUIDE.md # Catatan smart panning
└── ARCHITECTURE.md        # Diagram sistem dan arsitektur
```

## Troubleshooting

### Import Error: `"yt_dlp.YoutubeDL" could not be resolved`

Jika editor menandai import `yt_dlp` sebagai tidak ditemukan, itu normal ketika Anda tidak menginstall dependencies Python secara lokal — library `yt-dlp` hanya disediakan di image Docker untuk efisiensi.

Cara yang direkomendasikan: jalankan backend lewat Docker Compose (lihat Quick Start) sehingga semua dependency tersedia di container. Anda tidak perlu membuat `.venv` atau menginstall `yt-dlp` di mesin lokal.

### Download Gagal Karena Autentikasi / "Sign in to confirm"

Beberapa video YouTube meminta login atau verifikasi bot sehingga `yt-dlp` akan menolak download tanpa cookie. Untuk menangani ini:

- Ekspor cookie dari browser Anda (contoh menggunakan `yt-dlp` di host):

```bash
# di host (pastikan yt-dlp terinstall di host untuk langkah ini)
yt-dlp --cookies-from-browser chrome --cookies ./cookies.txt
```

- Mount file `cookies.txt` ke folder `/app/data` di container dan set variabel lingkungan `YT_COOKIES_FILE` ke path file tersebut, contohnya `/app/data/cookies.txt`.

Contoh potongan `docker-compose.yml` service backend:

```yaml
services:
  backend:
    build: ./backend
    environment:
      - YT_COOKIES_FILE=/app/data/cookies.txt
    volumes:
      - ./data:/app/data
```

Jika Anda lebih suka tidak mengekspor cookie, unduhan video tersebut mungkin tidak tersedia karena pembatasan dari YouTube.

### Docker Build Error: `git not found`

**Solusi:** Backend Dockerfile tidak memerlukan `git` lagi. Cukup jalankan:

```bash
docker compose build --no-cache backend
```

### Ollama Connection Error

Pastikan:
- Ollama sudah berjalan di Docker atau host, dan tersedia pada `http://host.docker.internal:11434`
- Backend Docker dapat mengakses `http://host.docker.internal:11434`
- Sudah ada model di Ollama: `ollama pull llama2` (atau model lain)

Jika menggunakan Ollama di container terpisah, pastikan port 11434 sudah dibuka dan volume model tersedia.

## Development Workflow

### Docker-first Workflow (Recommended)
1. Jalankan semua service dengan Docker Compose dari root project:
```bash
docker compose up --build
```
2. Edit kode di `backend/` atau `frontend/`, lalu periksa hasil di browser dan log container
3. Backend dependency sudah terinstall di container; tidak perlu `.venv` untuk workflow Docker
4. Jika perlu, jalankan frontend secara lokal untuk debugging UI cepat

### Optional Local Development
Jika Anda memilih mengembangkan lokal:
1. **Backend lokal:** buat `.venv` dan install dependency lokal
2. **Frontend lokal:** jalankan Vite seperti biasa
3. Proses Docker masih direkomendasikan untuk menjalankan backend secara konsisten

## Environment Variables

### Docker Compose / Docker-first
- Backend container menggunakan env dari `docker-compose.yml`
- `OLLAMA_URL=http://host.docker.internal:11434` untuk akses Ollama dari dalam container
- Jika perlu cookies yt-dlp, set `YT_COOKIES_FILE=/app/data/cookies.txt`

### Local Development
Jika menjalankan backend lokal, gunakan `.env` di root:
```env
OLLAMA_URL=http://localhost:11434
```

## .venv Folder & .gitignore

`.venv/` sudah di `.gitignore`, jadi folder ini:
- **TIDAK** akan di-commit ke Git
- **TIDAK** perlu di-share ke repository
- Dibuat hanya jika Anda menjalankan backend secara lokal

Jika menggunakan Docker Compose atau Dev Container, `.venv` tidak diperlukan.

## Command Shortcuts

**Docker-first:**
```bash
# Build and start everything
docker compose up --build

# Restart services after changes
docker compose restart

# Tail backend logs
docker compose logs -f backend
```

**Optional Local Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Optional Local Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Docker CLI:**
```bash
# Build backend image
docker compose build backend

# Run backend container only
docker compose up backend

# Cleanup
docker system prune -a --volumes
```

## Support

Jika ada error atau pertanyaan:
1. Cek `ARCHITECTURE.md` untuk diagram sistem
2. Cek `CLAUDE.md` untuk AI Guidelines
3. Baca log Docker: `docker logs ai_clipper_backend`
4. Baca log Frontend: cek console browser DevTools
