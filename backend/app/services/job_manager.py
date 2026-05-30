from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import sys
import asyncio
from rich.console import Console
from fastapi import WebSocket

console = Console(force_terminal=True, color_system="standard")

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
        self.step: str = ""
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
            "step": self.step,
            "progress": self.progress,
            "output_files": self.output_files,
            "error": self.error,
            "video_path": self.video_path,
            "transcript_path": self.transcript_path,
        }

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if self.loop is None:
            self.loop = asyncio.get_running_loop()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def _send_message(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            # Create a copy of the list to avoid RuntimeError if modified during iteration
            for connection in list(self.active_connections[job_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(job_id, connection)

    def broadcast(self, job_id: str, message: dict):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send_message(job_id, message), self.loop)

jobs: Dict[str, JobResult] = {}
ws_manager = ConnectionManager()

def create_job(job_id: str) -> JobResult:
    result = JobResult(job_id)
    jobs[job_id] = result
    return result

def get_job(job_id: str) -> Optional[JobResult]:
    return jobs.get(job_id)

_last_in_place = False
spinner_frames = ['/', '-', '\\', '|']
spinner_idx = 0

def update_job_status(job_id: str, status: JobState, message: str, step: str = "", progress: Optional[int] = None, error: Optional[str] = None, output_files: Optional[List[str]] = None, in_place: bool = True) -> None:
    global spinner_idx, _last_in_place
    job = jobs.get(job_id)
    if not job:
        return
    job.status = status
    job.message = message
    if step:
        job.step = step
    if progress is not None:
        job.progress = progress
    if error:
        job.error = error
    if output_files is not None:
        job.output_files = output_files
        
    # Broadcast to WebSocket clients
    ws_manager.broadcast(job_id, job.to_dict())
        
    # Log to terminal
    prog_str = f"[{job.progress}%] " if job.progress > 0 and status == JobState.running else ""
    if status == JobState.running:
        if in_place:
            spinner = spinner_frames[spinner_idx % len(spinner_frames)]
            spinner_idx += 1
            # Tambahkan banyak spasi untuk menghapus karakter sisa dari pesan sebelumnya yang lebih panjang
            console.print(f"[bold cyan][Job {job_id}][/bold cyan] {spinner} {prog_str}[yellow]{message}[/yellow]" + " " * 40, end="\r")
            sys.stdout.flush()
            _last_in_place = True
        else:
            if _last_in_place:
                console.print()
                _last_in_place = False
            console.print(f"[bold cyan][Job {job_id}][/bold cyan] {prog_str}[yellow]{message}[/yellow]")
    elif status == JobState.success:
        if _last_in_place:
            console.print()
            _last_in_place = False
        console.print(f"[bold green][Job {job_id}] ✓ {message}[/bold green]")
        if output_files:
            for f in output_files:
                console.print(f"  [dim]- {f}[/dim]")
    elif status == JobState.failed:
        if _last_in_place:
            console.print()
            _last_in_place = False
        console.print(f"[bold red][Job {job_id}] ✗ {message}[/bold red]")
        if error:
            console.print(f"  [red]Error: {error}[/red]")
    else:
        if _last_in_place:
            console.print()
            _last_in_place = False
        console.print(f"[bold blue][Job {job_id}][/bold blue] {message}")


def set_job_artifacts(job_id: str, video_path: str, transcript_path: str) -> None:
    job = jobs.get(job_id)
    if not job:
        return
    job.video_path = video_path
    job.transcript_path = transcript_path
