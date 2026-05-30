from pathlib import Path
from typing import List, Optional, Tuple, Union

import ffmpeg


def render_clip(
    video_path: Path,
    output_path: Path,
    start: float,
    end: float,
    crop_params: Union[Tuple[int, int, int, int], Tuple[int, int, List[Tuple[int, int, int]]]],
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = end - start
    input_stream = ffmpeg.input(str(video_path), ss=start, t=duration)
    video_stream = input_stream.video
    audio_stream = input_stream.audio

    if len(crop_params) == 4 and isinstance(crop_params[2], int):
        width, height, x, y = crop_params
        if width and height:
            video_stream = video_stream.crop(x, y, width, height)
    else:
        width, height, crop_positions = crop_params
        if crop_positions:
            x_expr = _build_crop_expression(crop_positions, axis="x")
            y_expr = _build_crop_expression(crop_positions, axis="y")
            video_stream = video_stream.crop(x=x_expr, y=y_expr, width=width, height=height)

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


def _build_crop_expression(crop_positions: List[Tuple[int, int, int]], axis: str = "x", max_points: int = 20) -> str:
    coord_index = 1 if axis == "x" else 2
    positions = _sample_crop_path(crop_positions, max_points)
    if len(positions) == 1:
        return str(positions[0][coord_index])

    expression = ""
    for index in range(len(positions) - 1):
        frame_idx, curr_x, curr_y = positions[index]
        next_frame_idx, next_x, next_y = positions[index + 1]
        coord = curr_x if axis == "x" else curr_y
        next_coord = next_x if axis == "x" else next_y

        if index == 0:
            expression = f"if(lt(n,{next_frame_idx}),{coord},"
        else:
            expression += f"if(lt(n,{next_frame_idx}),{coord}+({next_coord}-{coord})*(n-{frame_idx})/({next_frame_idx}-{frame_idx}),"

    expression += str(positions[-1][coord_index])
    expression += ")" * (len(positions) - 1)
    return expression


def _sample_crop_path(crop_positions: List[Tuple[int, int, int]], max_points: int = 20) -> List[Tuple[int, int, int]]:
    if len(crop_positions) <= max_points:
        return crop_positions

    interval = (len(crop_positions) - 1) / (max_points - 1)
    sampled: List[Tuple[int, int, int]] = []
    for idx in range(max_points):
        position_index = min(int(round(idx * interval)), len(crop_positions) - 1)
        sampled.append(crop_positions[position_index])

    return sampled


def safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)[:64]
