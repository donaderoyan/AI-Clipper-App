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


def _sample_crop_path(crop_positions: List[Tuple[int, int, int]], max_points: int = 40) -> List[Tuple[int, int, int]]:
    if len(crop_positions) <= max_points:
        return crop_positions

    critical_points = []
    # Identify critical points (snaps/cuts) where distance > 50px
    for i in range(1, len(crop_positions)):
        curr = crop_positions[i]
        prev = crop_positions[i-1]
        dist = ((curr[1] - prev[1])**2 + (curr[2] - prev[2])**2)**0.5
        if dist > 50.0:  
            if prev not in critical_points:
                critical_points.append(prev)
            if curr not in critical_points:
                critical_points.append(curr)

    # We MUST keep critical points so FFmpeg does an instant cut instead of a slow pan.
    remaining_budget = max_points - len(critical_points) - 2 # -2 for start and end
    
    uniform_points = []
    if remaining_budget > 0:
        step = len(crop_positions) / (remaining_budget + 1)
        for i in range(1, remaining_budget + 1):
            idx = int(i * step)
            if idx < len(crop_positions):
                uniform_points.append(crop_positions[idx])
    else:
        # If too many critical points (rare), we have to subsample them
        if len(critical_points) > max_points - 2:
            step = len(critical_points) / (max_points - 2)
            critical_points = [critical_points[int(i * step)] for i in range(max_points - 2)]

    all_sampled = set([crop_positions[0], crop_positions[-1]] + critical_points + uniform_points)
    
    # Sort chronologically
    final_path = sorted(list(all_sampled), key=lambda x: x[0])
    return final_path[:max_points]


def safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)[:64]
