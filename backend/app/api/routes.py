from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, HttpUrl, field_validator

from app.services.job_manager import create_job, get_job, ws_manager
from app.services.pipeline import run_ai_pipeline

router = APIRouter()

class ProcessRequest(BaseModel):
    url: HttpUrl
    aspect_ratio: str = "9:16"
    prompt_context: str = "Fokus pada momen historis yang absurd, tragis, atau unik. Cari hook yang kuat di awal."
    target_duration: int | None = None
    custom_timestamps: str | None = None
    output_count: int | None = None

    @field_validator('aspect_ratio')
    @classmethod
    def check_aspect(cls, v: str):
        if v not in ("9:16", "16:9"):
            raise ValueError('Rasio aspek tidak valid. Pilih "9:16" atau "16:9".')
        return v

    @field_validator('target_duration')
    @classmethod
    def check_duration(cls, v):
        if v is None:
            return v
        if v <= 0:
            raise ValueError('Durasi target harus angka positif.')
        return v

    @field_validator('output_count')
    @classmethod
    def check_count(cls, v):
        if v is None:
            return v
        if v <= 0:
            raise ValueError('Jumlah keluaran harus angka positif.')
        return v

    @field_validator('custom_timestamps')
    @classmethod
    def check_timestamps(cls, v):
        if v is None or v.strip() == "":
            return v
        import re
        pattern = re.compile(r'^(\\d{1,2}:\\d{2}(?::\\d{2})?)-(\\d{1,2}:\\d{2}(?::\\d{2})?)(\\s*,\\s*\\d{1,2}:\\d{2}(?::\\d{2})?-\\d{1,2}:\\d{2}(?::\\d{2})?)*$')
        if not pattern.match(v.strip()):
            raise ValueError('Format timestamp tidak valid. Contoh: 01:20-02:00, 05:00-06:30')
        return v

class ProcessResponse(BaseModel):
    status: str
    message: str
    job_id: str

class StatusResponse(BaseModel):
    status: str
    message: str
    job_id: str
    progress: int = 0
    output_files: list[str] = []
    error: str | None = None
    clips_metadata: list[dict] = []

@router.get("/")
def read_root():
    return {"status": "ok", "service": "AI Clipper Backend is running!"}

@router.post("/api/v1/process", response_model=ProcessResponse)
async def process_video(request: ProcessRequest, background_tasks: BackgroundTasks):
    try:
        import uuid
        job_id = str(uuid.uuid4())[:8]
        create_job(job_id)
        background_tasks.add_task(run_ai_pipeline, job_id, request)

        return ProcessResponse(
            status="accepted",
            message="Tugas masuk ke antrean pemrosesan.",
            job_id=job_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    return StatusResponse(
        status=job.status.value,
        message=job.message,
        job_id=job.job_id,
        progress=job.progress,
        output_files=job.output_files,
        error=job.error,
    )

@router.websocket("/api/v1/ws/status/{job_id}")
async def websocket_status(websocket: WebSocket, job_id: str):
    await ws_manager.connect(job_id, websocket)
    try:
        # Kirim status awal sesaat setelah terhubung
        job = get_job(job_id)
        if job:
            await websocket.send_json(job.to_dict())
            
        while True:
            # Tahan koneksi tetap terbuka, bisa menerima data jika diperlukan (ping)
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(job_id, websocket)
