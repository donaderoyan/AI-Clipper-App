import os
import re
import json
from typing import List, Dict, Optional

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")


def extract_highlights_from_text(transcript: str, prompt_context: str, segments: List[dict], target_duration: Optional[int] = None, output_count: int = 1) -> List[Dict[str, object]]:
    if target_duration:
        duration_instruction = f"PENTING: Target durasi setiap klip HARUS sekitar {target_duration} detik (waktu `end` dikurangi `start`). "
    else:
        duration_instruction = ""
        
    example_json = "[\n"
    for i in range(output_count):
        start_time = 12.5 + (i * 100)
        end_time = start_time + (target_duration if target_duration else 19.5)
        example_json += f'  {{"start": {start_time}, "end": {end_time}, "label": "Hook utama {i+1}", "topic": "Topik klip singkat {i+1}"}}'
        if i < output_count - 1:
            example_json += ",\n"
    example_json += "\n]"

    prompt = (
        "Kamu adalah asisten yang mencari highlight terbaik dari transkrip video. "
        f"Tentukan {output_count} segmen yang paling menarik, utuh, dan relevan. "
        f"{duration_instruction}"
        "Untuk setiap segmen, berikan JSON dengan field: start, end, label, dan topic. "
        "Topic harus berupa ringkasan singkat 3-8 kata yang menggambarkan inti klip. "
        "Berikan jawaban dalam format JSON list berikut tanpa teks lain:\n"
        f"{example_json}\n"
        f"Konteks tugas: {prompt_context}\n"
        f"Transkrip:\n{transcript[:8000]}"
    )

    try:
        response = requests.post(
            f"{OLLAMA_URL}/v1/completions",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "max_tokens": 400,
                "temperature": 0.3,
            },
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()
        text = content.get("choices", [])[0].get("text", "") if isinstance(content.get("choices"), list) else content.get("output", "")
    except Exception:
        return fallback_segments(segments, output_count, target_duration)

    highlights = parse_highlight_output(text)
    if highlights:
        return highlights
    return fallback_segments(segments, output_count, target_duration)


def parse_highlight_output(output: str) -> List[Dict[str, object]]:
    try:
        json_candidates = re.search(r"\[\s*\{.*?\}\s*\]", output, re.DOTALL)
        if json_candidates:
            candidate = output[json_candidates.start():json_candidates.end()]
            return json.loads(candidate)
    except Exception:
        pass

    timestamps = []
    for line in output.splitlines():
        match = re.search(r"(\d+(?:\.\d+)?)\s*[-–:]\s*(\d+(?:\.\d+)?)", line)
        if match:
            timestamps.append({
                "start": float(match.group(1)),
                "end": float(match.group(2)),
                "label": "highlight",
                "topic": "Video Clip"
            })
    return timestamps


def fallback_segments(segments: List[dict], output_count: int = 1, target_duration: Optional[int] = None) -> List[Dict[str, object]]:
    if not segments:
        return [{"start": 0.0, "end": 20.0, "label": "default", "topic": "Video Clip"} for _ in range(output_count)]

    fallbacks = []
    duration = target_duration if target_duration else 25.0
    
    total_segments = len(segments)
    step = max(1, total_segments // output_count)
    
    for i in range(output_count):
        idx = min(i * step, total_segments - 1)
        candidate = segments[idx]
        start_time = float(candidate.get("start", 0.0))
        end_time = float(min(start_time + duration, segments[-1].get("end", start_time + duration)))
        fallbacks.append({
            "start": start_time,
            "end": end_time,
            "label": f"fallback_{i+1}",
            "topic": f"Klip fallback {i+1}"
        })
        
    return fallbacks
