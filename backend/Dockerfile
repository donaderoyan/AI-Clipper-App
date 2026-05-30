# Gunakan tag spesifik (bookworm) agar repositori apt lebih stabil
FROM python:3.12-slim-bookworm

# Tambahkan argumen untuk menonaktifkan interaksi frontend selama instalasi
ENV DEBIAN_FRONTEND=noninteractive

# Menginstal dependensi sistem yang wajib untuk Video & Computer Vision
RUN apt-get clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Menetapkan direktori kerja di dalam container
WORKDIR /app

# Menyalin requirements dan menginstal dependensi Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Menyalin seluruh kode backend
COPY . .

# Membuka port FastAPI
EXPOSE 8000

# Menjalankan server uvicorn (menunggu perintah)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]