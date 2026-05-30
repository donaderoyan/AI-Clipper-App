import traceback
from pathlib import Path
from typing import List, Dict

from .analyzer import extract_highlights_from_text
from .downloader import download_video
from .renderer import render_clip, safe_filename
from .transcriber import transcribe_video, generate_clip_srt
from .vision import calculate_crop, calculate_crop_path
from .job_manager import JobState, update_job_status, set_job_artifacts
from ..utils.storage import RAW_DIR, WORK_DIR, OUTPUT_DIR


def time_to_sec(t_str: str) -> float:
    parts = t_str.split(':')
    parts.reverse()
    sec = 0.0
    for i, p in enumerate(parts):
        sec += float(p) * (60 ** i)
    return sec

def format_time(sec: float) -> str:
    s = int(sec)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

def parse_custom_timestamps(ts_str: str) -> List[Dict[str, float]]:
    results = []
    for part in ts_str.split(','):
        part = part.strip()
        if not part: continue
        times = part.split('-')
        if len(times) == 2:
            try:
                start_sec = time_to_sec(times[0].strip())
                end_sec = time_to_sec(times[1].strip())
                results.append({
                    'start': start_sec,
                    'end': end_sec,
                    'label': f'custom_{int(start_sec)}_{int(end_sec)}'
                })
            except Exception:
                pass
    return results


def run_ai_pipeline(job_id: str, request_data) -> None:
    try:
        update_job_status(job_id, JobState.running, "Memulai pipeline AI...", step="init", progress=5)

        raw_dir = RAW_DIR / job_id
        work_dir = WORK_DIR / job_id
        output_dir = OUTPUT_DIR / job_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        update_job_status(job_id, JobState.running, "Mempersiapkan unduhan video...", step="prepare_download", progress=8)
        
        def dl_progress(percent_str):
            update_job_status(job_id, JobState.running, f"Mengunduh video... {percent_str}", step="download", progress=10, in_place=True)
            
        video_path = download_video(request_data.url, raw_dir, progress_callback=dl_progress)
        
        update_job_status(job_id, JobState.running, "Mengekstrak audio dan transkripsi video...", step="transcribe", progress=40, in_place=True)
        transcript_text, transcript_path, segments = transcribe_video(video_path, work_dir)
        set_job_artifacts(job_id, str(video_path), str(transcript_path))

        update_job_status(job_id, JobState.running, "Menganalisis transkrip untuk menemukan highlight...", step="analyze", progress=70, in_place=True)
        target_duration = getattr(request_data, 'target_duration', None)
        output_count = getattr(request_data, 'output_count', None)

        actual_output_count = 1
        if output_count is not None:
            if target_duration is not None:
                total_duration = segments[-1].get("end", 0.0) if segments else 0.0
                max_clips = int(total_duration // target_duration)
                actual_output_count = min(output_count, max_clips) if max_clips > 0 else 1
            else:
                actual_output_count = output_count

        highlights = extract_highlights_from_text(transcript_text, request_data.prompt_context, segments, target_duration, actual_output_count)
        if not highlights:
            highlights = [{"start": 0.0, "end": min(20.0, segments[-1].get("end", 20.0) if segments else 20.0), "label": "default"}]
            
        if target_duration is not None:
            max_end = segments[-1].get("end", 0.0) if segments else 0.0
            for hl in highlights:
                cur_max_end = max_end if max_end > 0 else hl.get("end", 0.0)
                # Ensure the clip is exactly target_duration (if video is long enough)
                if hl["start"] + target_duration > cur_max_end:
                    hl["start"] = max(0.0, cur_max_end - target_duration)
                    hl["end"] = min(cur_max_end, hl["start"] + target_duration)
                else:
                    hl["end"] = hl["start"] + target_duration

        final_clips = []
        custom_ts = getattr(request_data, 'custom_timestamps', None)
        if custom_ts:
            final_clips.extend(parse_custom_timestamps(custom_ts))
        
        if not custom_ts or target_duration is not None:
            # If no custom timestamps, or if target_duration is provided, include the AI clip
            final_clips.extend(highlights[:actual_output_count])

        # Dedup just in case
        unique_clips = []
        seen = set()
        for clip in final_clips:
            k = (clip['start'], clip['end'])
            if k not in seen:
                seen.add(k)
                unique_clips.append(clip)

        output_files = []
        
        total_clips = len(unique_clips)
        for i, clip in enumerate(unique_clips):
            label = clip.get('label', f'clip_{i}')
            start_val = int(clip['start'])
            end_val = int(clip['end'])
            dur_val = end_val - start_val
            
            # Calculate smart crop dynamically for this specific clip
            target_width, target_height, crop_positions = calculate_crop_path(
                video_path,
                request_data.aspect_ratio,
                float(clip["start"]),
                float(clip["end"]),
            )
            crop_params = (target_width, target_height, crop_positions)
            
            if label.startswith('custom_'):
                desc_name = f"custom_timestamp_{start_val}s_to_{end_val}s"
            else:
                desc_name = f"ai_clip_target_{dur_val}s_{label}"
                
            output_filename = f"{safe_filename(desc_name)}_{job_id}_{i}.mp4"
            output_path = output_dir / output_filename
            output_srt_path = output_path.with_suffix(".srt")

            prog = 80 + int((i / total_clips) * 15)
            start_fmt = format_time(float(clip["start"]))
            end_fmt = format_time(float(clip["end"]))
            update_job_status(job_id, JobState.running, f"Merender klip {start_fmt} hingga {end_fmt}...", step=f"render_{i}", progress=prog)
            
            generate_clip_srt(segments, float(clip["start"]), float(clip["end"]), output_srt_path)
            
            render_clip(
                video_path=video_path,
                output_path=output_path,
                start=float(clip["start"]),
                end=float(clip["end"]),
                crop_params=crop_params,
            )
            output_files.append(str(output_path))
            output_files.append(str(output_srt_path))

        update_job_status(job_id, JobState.success, "Proses selesai.", step="done", progress=100, output_files=output_files)
    except Exception as exc:
        error_message = str(exc)
        if hasattr(exc, "stderr") and exc.stderr:
            try:
                error_message = exc.stderr.decode('utf-8')
            except Exception:
                error_message = str(exc.stderr)
        traceback.print_exc()
        update_job_status(job_id, JobState.failed, "Terjadi kesalahan selama pemrosesan.", step="error", error=error_message)
