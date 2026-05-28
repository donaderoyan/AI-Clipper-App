# Panduan AI (AI Assistant Guidelines)

## Konteks Proyek
Ini adalah Web App untuk memotong video panjang menjadi video pendek vertikal (9:16) atau horizontal (16:9) secara otomatis menggunakan AI lokal. Aplikasi ini menggunakan arsitektur Local Microservice: Electron (Frontend) dan FastAPI Python (Backend).

## Fokus Aplikasi
Memproses penceritaan bergaya dokumenter, menemukan momen puncak narasi (seperti insiden historis, fakta tragis/unik), melakukan pemotongan, smart panning, dan menambahkan subtitle dinamis.

## Tech Stack
- **Frontend:** Electron, TypeScript, React (atau Vite), Tailwind CSS.
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

## Aturan Penulisan Kode (Coding Conventions)
- **Penanganan Error:** Selalu berikan blok `try-except` di Python, terutama saat memanggil subproses seperti FFmpeg atau yt-dlp, dan kembalikan status HTTP yang sesuai (400, 500) ke frontend.
- **Bahasa Komentar:** Gunakan Bahasa Indonesia atau Bahasa Inggris yang jelas dan ringkas.
- **TypeScript:** Gunakan strict typing. Hindari `any`. Gunakan interface untuk payload API.
- **Python:** Gunakan Type Hints (misal: `def process_video(url: str) -> dict:`). Tulis kode dengan gaya asinkron (`async def`) untuk endpoint API.
- **Komunikasi API:** Frontend dan Backend HANYA berkomunikasi melalui HTTP REST API (localhost:8000). Jangan gunakan IPC Electron untuk memanggil skrip Python.
- **Ollama API:** Backend di dalam Docker harus mengakses Ollama yang berjalan di Host Windows menggunakan URL `http://host.docker.internal:11434`.
- **Path Storage:** Selalu simpan dan baca file media menggunakan path absolut yang mengarah ke direktori `/app/data` di dalam backend, yang otomatis tersinkronisasi ke folder `./data` di Host.