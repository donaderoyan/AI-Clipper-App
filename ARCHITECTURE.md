# Arsitektur Sistem: AI Video Clipper

## Ringkasan Eksekutif
Sistem ini menggunakan arsitektur Hybrid-Container. Antarmuka pengguna (Electron) berjalan secara native di sistem operasi Host (Windows) untuk memastikan performa GUI maksimal. Mesin pemrosesan (Python/FastAPI) diisolasi di dalam Docker Container untuk menyelesaikan masalah dependensi kompleks seperti FFmpeg dan OpenCV.

## Diagram Arsitektur Infrastruktur

* **Host OS (Windows):**
    * Electron GUI (Frontend)
    * Ollama Service (Local LLM Engine - berjalan di Host untuk akses GPU optimal)
    * Folder `/data` (Penyimpanan media aktual)
* **Docker Container (Linux/Backend):**
    * FastAPI (REST Server)
    * FFmpeg & OpenCV (System level)
    * Python Libraries (yt-dlp, faster-whisper)
    * Mount Volume: Mengakses `/data` dari Host.

## Diagram Alur Data (Data Flow)

1. **Input Frontend:** 
   - Pengguna memasukkan URL video (YouTube).
   - Pengguna memilih pengaturan (rasio 9:16, 16:9).
   - Pengguna bisa memasukan prompt untuk AI context.
   - Pengguna target duration.
   - Pengguna bisa memasukan angka berapa banyak output video yang diinginkan. (Perlu validasi atau penanganan extra disini, jika video sumber 10 menit, dan target duration adalah 3 menit, maka output video paling banyak adalah 3 buah dengan durasi 3 menit. Tapi jika input jumlah berapa banyak output video yang diinginkan adalah 5, maka akan diabaikan dan respect pada rule ini)
   - Pengguna bisa memasukan custom timestamps.
   
2. **Request:** UI mengirim HTTP POST ke `http://localhost:8000/api/v1/process`.
3. **Backend Pipeline (Docker Container):**
   - Container memiliki instalasi FFmpeg dan pustaka sistem secara native.
   - Python di dalam Docker mengeksekusi pipeline:
      - `yt-dlp` Unduh video simpan ke `/app/data/raw/` (otomatis muncul di Windows).
      - `faster-whisper` mengekstrak audio menjadi teks (.srt).
      - Analisis teks dengan mengirim HTTP Request keluar container menuju `http://host.docker.internal:11434` (Ollama di Windows).
      - `Ollama (LLM)` menganalisis teks untuk menemukan *timestamp* terbaik (momen puncak/menarik).
      - `OpenCV` menganalisis frame untuk *smart panning* (jika mode vertikal).
      - `FFmpeg` memotong video, menyesuaikan rasio, dan menempelkan subtitle.
   - Semua file ditulis ke folder `/app/data` di dalam container.
4. **Volume Mapping:** Folder `/app/data` di container dipetakan ke folder `/data` di Windows. Electron dapat langsung melihat dan membuka video hasil render dari folder tersebut.
5. **Response/Polling:** Selama proses, frontend terus melakukan polling ke endpoint `/status` atau mendengarkan WebSockets untuk memperbarui *progress bar*.
   - Frontend S
6. **Output:** Video selesai dirender di folder lokal, UI menampilkan notifikasi sukses. File subtitle .srt tersimpan dalam folder yang sama dengan video.

## Frondend UI/UX
1. Single page dibagi menjadi 2 bagian, bagian kiri untuk form user dan bagian kanan untuk terminal UI.
2. Bagian kiri dibuat sebagai sidebar. Logo aplikasi menyatu dibagian atas, dibagian bawahnya form user.
3. Bagian kanan dibagi menjadi 2, bagian atas mempilkan terminal UI bagian bawah untuk menampilan hasil video clipping.
   	**Bagian Terminal UI:**
			Informasi yang ditampilkan seharusnya informatif, user friendly, clean, dan menarik. Saat menampilkan status pipeline di terminal UI, yang berubah itu datanya jangan langsung print berulang-ulang. Informasi yang ditampilan berdasarkan proses pipeline/job status dan setiap bagian prosesnya harus ganti line. Berikut adalah job status:
				* Downloading video
						- Tampilkan persentase download
				* Proses mengekstrak audio dan transkripsi video
						- Tampilkan loading indicator proses mengekstrak audio dan transkripsi video
				* Menganalisis transkrip video
						- Tampilkan loading indicator proses untuk transkrip video
				* Merender klip
						- Tampilkan loading indicator dan presentase proses untuk merender klip video.
						- Sesuaikan dengan jumlah output yang diinginkan.
				* Proses selesai
		**Bagian Hasil Video Clipping:**


## Struktur Folder (Directory Tree)

```text
/ai-clipper-app
│
├── docker-compose.yml        # Orkestrasi Docker
├── CLAUDE.md                 # Panduan untuk AI/Cursor IDE
├── ARCHITECTURE.md           # Peta arsitektur sistem
├── .gitignore
│
├── /frontend                 # ELECRON + REACT + TYPESCRIPT
│   ├── /src
│   │   ├── /components       # Komponen UI (Tombol, Progress Bar)
│   │   ├── /services         # Fungsi pemanggil API ke localhost:8000
│   │   ├── App.tsx           # Layar utama aplikasi
│   │   └── main.ts           # Konfigurasi main process Electron
│   ├── package.json
│   └── vite.config.ts
│
├── /backend                  # PYTHON + FASTAPI (Di-build menjadi Docker Image)
│   ├── /app
│   │   ├── main.py           # Entry point FastAPI
│   │   ├── /api              # Endpoint router (routes)
│   │   │   └── routes.py
│   │   ├── /services         # Logika AI dan Media
│   │   │   ├── downloader.py # Pembungkus yt-dlp
│   │   │   ├── transcriber.py# Pembungkus faster-whisper
│   │   │   ├── analyzer.py   # Interaksi dengan Ollama/LLM
│   │   │   ├── vision.py     # Logika OpenCV / Panning
│   │   │   └── renderer.py   # Eksekusi FFmpeg
│   │   └── /utils            # Helper fungsi dasar
│   ├── Dockerfile            # Resep image backend
│   ├── .dockerignore         # [BARU] Mengabaikan file saat build image
│   ├── requirements.txt      # Daftar dependensi Python
│   └── .env                  # Variabel lingkungan lokal
│
└── /data                     # (Volume bersama / Shared bind mount)
    ├── /raw                  # Unduhan video asli
    ├── /temp                 # File audio, srt sementara
    └── /output               # Hasil akhir video pendek