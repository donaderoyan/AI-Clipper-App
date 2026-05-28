from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.routes import router as api_router
from app.utils.storage import ensure_data_directories

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

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)