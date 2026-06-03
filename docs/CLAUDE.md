# Panduan AI (AI Assistant Guidelines)

## Konteks Proyek
Ini adalah Web App untuk memotong video panjang menjadi video pendek vertikal (9:16) atau horizontal (16:9) secara otomatis menggunakan AI lokal. Aplikasi ini menggunakan arsitektur Local Microservice: Electron (Frontend) dan FastAPI Python (Backend).

## Fokus Aplikasi
Memproses penceritaan bergaya dokumenter, menemukan momen puncak narasi (seperti insiden historis, fakta tragis/unik), melakukan pemotongan, smart panning, dan menambahkan subtitle dinamis.
- Setiap klip dilengkapi metadata topik dan rentang waktu, lalu ditampilkan dengan detail dalam hover popup.
- Pemutar video modal menggunakan kontrol HTML5 standar sehingga seek bar atau timeline bisa digunakan untuk melompat ke menit yang diinginkan.

## Tech Stack
- **Frontend:** Electron, TypeScript, React (Vite), Material UI (MUI).
- **Backend:** Python 3.10+, FastAPI, Docker, Docker Compose.
- **Infrastruktur:** Docker & Docker Compose (untuk Backend & dependensi OS seperti FFmpeg).
- **Pemrosesan AI & Media:** yt-dlp, faster-whisper, Ollama (Local LLM), OpenCV, FFmpeg.

## Struktur Direktori Utama
- `/frontend`: Antarmuka desktop (berjalan di Windows/Host).
- `/backend`: Server FastAPI dan pipeline AI (Dockerized).
- `/data`: Volume bersama (Shared volume) antara Host OS dan Docker Container untuk menyimpan video dan transkrip.

## Dev Commands
Jika saya meminta untuk "jalankan proyek", jalankan dua perintah ini di terminal terpisah:
1. Backend (Docker): `docker-compose up --build`
2. Frontend (Native): `cd frontend && npm run dev`

## Download Caching
Ketika pengguna mengirimkan URL video, backend akan terlebih dahulu memeriksa apakah video tersebut sudah diunduh sebelumnya ke dalam folder `/data/raw`. Jika file yang ada cocok dengan `id` video dan ekstensi ditemukan, backend akan menggunakan kembali file tersebut alih-alih mengunduhnya lagi. Ini mengurangi bandwidth, mempercepat operasi berulang, dan menghindari unduhan yang tidak perlu ketika URL yang sama diproses beberapa kali.

Untuk memaksa pengunduhan ulang, hapus file yang sesuai di host `/data/raw/<video_id>.*` atau bersihkan direktori `/data/raw`.

Pengguna akan melihat pesan di Terminal UI:
- Jika cache tersedia: **✓ Video sudah diunduh sebelumnya (menggunakan cache)**
- Jika download baru: **✓ Video berhasil diunduh**

## Smart Panning (Vision Panning Improvements)
Backend menggunakan OpenCV untuk menganalisis video dan menghasilkan koordinat crop dinamis yang mengikuti wajah orang yang sedang berbicara (speaker). Fitur ini mencakup:

1. **Multi-Speaker & Profile Detection**: Sistem dapat mendeteksi multiple orang dalam satu frame dan secara otomatis fokus ke orang yang sedang berbicara. Dan sistem juga mendeteksi wajah lurus (frontal) maupun menyamping (profil kiri/kanan), dan mengelompokkannya secara cerdas.

2. **Speaker Scoring Algorithm (Net Optical Flow)**: 
   - **Prioritas Utama (Net Mouth Flow)**: Menghitung selisih pergerakan bibir dan pergerakan kepala. Orang yang sekadar mengangguk tidak akan dihitung, hanya yang benar-benar berbicara yang mendapat skor tertinggi.
   - **Static Penalty**: Objek yang sama sekali tidak bergerak (seperti poster/corak dinding) diberi penalti mutlak agar kamera tidak mengunci objek mati.
   - **Spatial Hysteresis**: Memanfaatkan koordinat spasial (*last_valid_focus*) untuk menjaga agar kamera setia pada pembicara, meskipun AI pendeteksi sesaat gagal (berkedip).

3. **Smart EMA Tracking & Keyframe Protection**:
   - **EMA (Exponential Moving Average)**: Mengikuti orang yang berjalan dengan sangat mulus.
   - **Snap Threshold**: Jika target bergerak > 150 pixel dalam waktu singkat (indikasi berganti pembicara), kamera akan melompat seketika (Cut).
   - **FFmpeg Protection**: Frame kritis saat terjadinya *Snap* dilindungi dari *subsampling*, sehingga FFmpeg melakukan pemotongan transisi 0 detik tanpa melayang-layang di bagian tengah layar.

## Aturan Penulisan Kode (Coding Conventions)
- **Penanganan Error:** Selalu berikan blok `try-except` di Python, terutama saat memanggil subproses seperti FFmpeg atau yt-dlp, dan kembalikan status HTTP yang sesuai (400, 500) ke frontend.
- **Bahasa Komentar:** Gunakan Bahasa Indonesia atau Bahasa Inggris yang jelas dan ringkas.
- **TypeScript:** Gunakan strict typing. Hindari `any`. Gunakan interface untuk payload API.
- **Form Validation / UX:** Berikan validasi form yang jelas dan pesan error langsung di UI untuk URL, durasi target, jumlah output, dan format timestamp.
- **Python:** Gunakan Type Hints (misal: `def process_video(url: str) -> dict:`). Tulis kode dengan gaya asinkron (`async def`) untuk endpoint API.
- **Komunikasi API:** Frontend dan Backend HANYA berkomunikasi melalui HTTP REST API (localhost:8000). Jangan gunakan IPC Electron untuk memanggil skrip Python.
- **Ollama API:** Backend di dalam Docker harus mengakses Ollama yang berjalan di Host Windows menggunakan URL `http://host.docker.internal:11434`.
- **Path Storage:** Selalu simpan dan baca file media menggunakan path absolut yang mengarah ke direktori `/app/data` di dalam backend, yang otomatis tersinkronisasi ke folder `./data` di Host.