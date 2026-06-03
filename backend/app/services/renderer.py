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

    # Always keep first and last points
    sampled = [crop_positions[0]]
    
    # Calculate step to consider
    # Instead of purely uniform, we look for significant movement
    last_added = crop_positions[0]
    
    # We want to keep points that represent a significant change in position (panning)
    # and also keep some evenly spaced points for general tracking
    threshold = 20  # pixels difference to consider it a significant move
    
    candidates = []
    for i in range(1, len(crop_positions) - 1):
        curr = crop_positions[i]
        prev = crop_positions[i-1]
        next_pos = crop_positions[i+1]
        
        # Check if this point is a "corner" (start or end of a pan)
        dist_prev = ((curr[1] - prev[1])**2 + (curr[2] - prev[2])**2)**0.5
        dist_next = ((next_pos[1] - curr[1])**2 + (next_pos[2] - curr[2])**2)**0.5
        
        # Keep point if speed changes significantly OR if there is a large movement (fast pan)
        if abs(dist_prev - dist_next) > 5.0 or dist_prev > 30.0:
            candidates.append(curr)
            
    # If we have too many candidates, subsample them
    if len(candidates) > max_points - 2:
        step = len(candidates) / (max_points - 2)
        filtered_candidates = [candidates[int(i * step)] for i in range(max_points - 2)]
    else:
        # If too few, fill with evenly spaced points
        filtered_candidates = candidates
        remaining = (max_points - 2) - len(filtered_candidates)
        if remaining > 0:
            interval = len(crop_positions) / (remaining + 1)
            for i in range(1, remaining + 1):
                idx = min(int(i * interval), len(crop_positions) - 1)
                if crop_positions[idx] not in filtered_candidates:
                    filtered_candidates.append(crop_positions[idx])
                    
    # Sort by frame index to maintain chronological order
    filtered_candidates.sort(key=lambda x: x[0])
    
    for pt in filtered_candidates:
        if pt not in sampled:
            sampled.append(pt)
            
    if crop_positions[-1] not in sampled:
        sampled.append(crop_positions[-1])

    return sampled[:max_points]


def safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)[:64]
