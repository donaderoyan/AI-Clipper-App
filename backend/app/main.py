from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import re
import os

from app.api.routes import router as api_router
from app.utils.storage import ensure_data_directories, OUTPUT_DIR

# Inisialisasi Aplikasi FastAPI
app = FastAPI(
    title="AI Video Clipper API",
    description="Local Microservice untuk memotong video menggunakan AI",
    version="1.0.0"
)

# Pengaturan CORS (Penting untuk komunikasi dengan Electron)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Dalam produksi, batasi ke origin Electron
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_data_directories()

@app.get("/media/{path:path}")
@app.head("/media/{path:path}")
def stream_media(path: str, request: Request):
    file_path = OUTPUT_DIR / path
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
        
    file_size = file_path.stat().st_size
    range_header = request.headers.get('Range', None)
    
    if range_header:
        byte1, byte2 = 0, None
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            groups = match.groups()
            byte1 = int(groups[0])
            if groups[1]:
                byte2 = int(groups[1])
                
        byte2 = byte2 if byte2 is not None else file_size - 1
        length = byte2 - byte1 + 1
        
        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)
            
        headers = {
            'Content-Range': f'bytes {byte1}-{byte2}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
            'Content-Type': 'video/mp4' if path.endswith('.mp4') else 'application/octet-stream',
        }
        return Response(data, status_code=206, headers=headers, media_type=headers['Content-Type'])
    else:
        with open(file_path, 'rb') as f:
            data = f.read()
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size),
            'Content-Type': 'video/mp4' if path.endswith('.mp4') else 'application/octet-stream',
        }
        return Response(data, status_code=200, headers=headers, media_type=headers['Content-Type'])

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)