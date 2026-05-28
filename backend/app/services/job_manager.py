from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from rich.console import Console

console = Console()

class JobState(str, Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"

class JobResult:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status: JobState = JobState.queued
        self.message: str = "Menunggu pemrosesan."
        self.progress: int = 0
        self.output_files: List[str] = []
        self.error: Optional[str] = None
        self.video_path: Optional[str] = None
        self.transcript_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "message": self.message,
            "progress": self.progress,
            "output_files": self.output_files,
            "error": self.error,
            "video_path": self.video_path,
            "transcript_path": self.transcript_path,
        }

jobs: Dict[str, JobResult] = {}


def create_job(job_id: str) -> JobResult:
    result = JobResult(job_id)
    jobs[job_id] = result
    return result


def get_job(job_id: str) -> Optional[JobResult]:
    return jobs.get(job_id)


def update_job_status(job_id: str, status: JobState, message: str, progress: Optional[int] = None, error: Optional[str] = None, output_files: Optional[List[str]] = None) -> None:
    job = jobs.get(job_id)
    if not job:
        return
    job.status = status
    job.message = message
    if progress is not None:
        job.progress = progress
    if error:
        job.error = error
    if output_files is not None:
        job.output_files = output_files
        
    # Log to terminal
    prog_str = f"[{job.progress}%] " if job.progress > 0 and status == JobState.running else ""
    if status == JobState.running:
        console.print(f"[bold cyan][Job {job_id}][/bold cyan] {prog_str}[yellow]{message}[/yellow]")
    elif status == JobState.success:
        console.print(f"[bold green][Job {job_id}] ✓ {message}[/bold green]")
        if output_files:
            for f in output_files:
                console.print(f"  [dim]- {f}[/dim]")
    elif status == JobState.failed:
        console.print(f"[bold red][Job {job_id}] ✗ {message}[/bold red]")
        if error:
            console.print(f"  [red]Error: {error}[/red]")
    else:
        console.print(f"[bold blue][Job {job_id}][/bold blue] {message}")


def set_job_artifacts(job_id: str, video_path: str, transcript_path: str) -> None:
    job = jobs.get(job_id)
    if not job:
        return
    job.video_path = video_path
    job.transcript_path = transcript_path
