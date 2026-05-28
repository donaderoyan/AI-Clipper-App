from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.services.job_manager import create_job, get_job
from app.services.pipeline import run_ai_pipeline

router = APIRouter()

class ProcessRequest(BaseModel):
    url: str
    aspect_ratio: str = "9:16"
    prompt_context: str = "Fokus pada momen historis yang absurd, tragis, atau unik. Cari hook yang kuat di awal."
    target_duration: int | None = None
    custom_timestamps: str | None = None

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
