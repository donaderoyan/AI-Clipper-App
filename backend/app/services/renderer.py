import shlex
from pathlib import Path
from typing import List, Optional, Tuple

import ffmpeg


def render_clip(
    video_path: Path,
    output_path: Path,
    start: float,
    end: float,
    crop_params: Tuple[int, int, int, int],
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height, x, y = crop_params

    duration = end - start
    input_stream = ffmpeg.input(str(video_path), ss=start, t=duration)
    video_stream = input_stream.video
    audio_stream = input_stream.audio

    if width and height and (x or y or width != 0):
        video_stream = video_stream.crop(x, y, width, height)

    ffmpeg_output = ffmpeg.output(
        video_stream,
        audio_stream,
        str(output_path),
        vcodec="libx264",
        acodec="aac",
        preset="fast",
        crf=23,
        movflags="+faststart",
    ).overwrite_output()

    ffmpeg_output.run(quiet=True, capture_stdout=True, capture_stderr=True)
    return output_path


def safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)[:64]
