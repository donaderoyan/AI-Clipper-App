# AI Video Clipper

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

Semua layanan frontend dan backend bisa dijalankan sepenuhnya di Docker. Ini membantu menghindari masalah dependensi lokal seperti `cv2` atau `ffmpeg`.

1. Build dan jalankan semua layanan dengan Docker Compose:

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

3. Hentikan layanan dengan:

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
├── frontend/          # Electron + React + TypeScript
├── backend/           # FastAPI + Python (Docker)
├── data/              # Shared volume (raw, temp, output)
├── docker-compose.yml # Orkestrasi Docker
└── README.md          # File ini
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
docker-compose build --no-cache backend
```

### Ollama Connection Error

Pastikan:
- Ollama running di Windows: `ollama serve`
- Backend Docker dapat mengakses host melalui `http://host.docker.internal:11434`
- Sudah ada model di Ollama: `ollama pull llama2` (atau model lain)

## Development Workflow

### Jika pakai Dev Container (Option A) - Recommended:
1. Semua dependencies sudah di container
2. Cukup edit file → auto-reload via volume mount
3. Tidak perlu khawatir dengan `.venv` atau system dependencies

### Jika pakai Local Development (Option B):
1. **Backend Changes:** Edit di `/backend/app/services/` → jalankan ulang manual atau gunakan `--reload` flag
2. **Frontend Changes:** Edit di `/frontend/src/` → auto-reload via Vite
3. **requirements.txt Changes:** Reinstall dengan `pip install -r backend/requirements.txt`

## Environment Variables

### Option A: Dev Container
- Menggunakan env dari `docker-compose.yml`
- `OLLAMA_URL=http://host.docker.internal:11434` (sudah default)

### Option B: Local Development
- Gunakan `.env` file di root (optional):
```env
OLLAMA_URL=http://localhost:11434
```

## .venv Folder & .gitignore

`.venv/` sudah di `.gitignore`, jadi folder ini:
- **TIDAK** akan di-commit ke Git
- **TIDAK** perlu di-share ke repository
- Jika clone project, folder ini harus dibuat ulang dengan `python -m venv .venv`

**Jika menggunakan Dev Container (Option A), Anda tidak perlu `.venv` sama sekali** - semua ada di Docker.

## Command Shortcuts

**Dev Container (Option A):**
```bash
# Semua command berjalan di dalam container
# Backend sudah running otomatis
# Hanya perlu jalankan frontend di terminal baru
cd frontend && npm run dev
```

**Local Development + Docker Frontend (Option B):**
```bash
# Terminal 1: Backend lokal
.venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

**Docker CLI:**
```bash
# Build backend image
docker-compose build backend

# Run backend container
docker-compose up backend

# Cleanup
docker system prune -a --volumes
```

## Support

Jika ada error atau pertanyaan:
1. Cek `ARCHITECTURE.md` untuk diagram sistem
2. Cek `CLAUDE.md` untuk AI Guidelines
3. Baca log Docker: `docker logs ai_clipper_backend`
4. Baca log Frontend: cek console browser DevTools
