import os
from pathlib import Path
from typing import List, Tuple

import ffmpeg
from faster_whisper import WhisperModel

MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
MODEL = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def extract_audio(video_path: Path, audio_path: Path) -> None:
    ensure_directory(audio_path.parent)
    (ffmpeg
        .input(str(video_path))
        .output(str(audio_path), format="wav", ac=1, ar="16000")
        .overwrite_output()
        .run(quiet=True, capture_stdout=True, capture_stderr=True))


def transcribe_video(video_path: Path, work_dir: Path) -> Tuple[str, Path, List[dict]]:
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_path = work_dir / "audio.wav"
    extract_audio(video_path, audio_path)

    segments_gen, _info = MODEL.transcribe(str(audio_path), beam_size=5)
    segments = list(segments_gen)
    transcript_text = "\n".join(segment.text.strip() for segment in segments if segment.text.strip())

    srt_path = work_dir / "transcript.srt"
    with srt_path.open("w", encoding="utf-8") as stream:
        for index, segment in enumerate(segments, start=1):
            start_time = segment.start
            end_time = segment.end
            stream.write(f"{index}\n")
            stream.write(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}\n")
            stream.write(f"{segment.text.strip()}\n\n")

    timestamps = [
        {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
        for segment in segments
    ]

    return transcript_text, srt_path, timestamps


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_clip_srt(segments: List[dict], clip_start: float, clip_end: float, output_srt_path: Path) -> None:
    with output_srt_path.open("w", encoding="utf-8") as stream:
        index = 1
        for seg in segments:
            seg_start = seg.get("start", 0.0)
            seg_end = seg.get("end", 0.0)
            
            # Skip if there's no overlap
            if seg_end <= clip_start or seg_start >= clip_end:
                continue
                
            # Adjust timestamps relative to clip start
            adj_start = max(0.0, seg_start - clip_start)
            adj_end = min(clip_end - clip_start, seg_end - clip_start)
            
            stream.write(f"{index}\n")
            stream.write(f"{format_timestamp(adj_start)} --> {format_timestamp(adj_end)}\n")
            stream.write(f"{seg.get('text', '')}\n\n")
            index += 1
