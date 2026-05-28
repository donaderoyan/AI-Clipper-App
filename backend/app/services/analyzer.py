import os
import re
from typing import List, Dict, Optional

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")


def extract_highlights_from_text(transcript: str, prompt_context: str, segments: List[dict], target_duration: Optional[int] = None) -> List[Dict[str, float]]:
    if target_duration:
        example_end = 12.5 + target_duration
        duration_instruction = f"PENTING: Target durasi klip HARUS sekitar {target_duration} detik (waktu `end` dikurangi `start`). "
    else:
        example_end = 32.0
        duration_instruction = ""

    prompt = (
        "Kamu adalah asisten yang mencari highlight terbaik dari transkrip video. "
        "Tentukan satu segmen yang paling menarik, utuh, dan relevan. "
        f"{duration_instruction}"
        "Berikan jawaban dalam format JSON berikut tanpa teks lain:\n"
        f"[{{\"start\": 12.5, \"end\": {example_end}, \"label\": \"Hook utama\"}}]\n"
        f"Konteks tugas: {prompt_context}\n"
        f"Transkrip:\n{transcript[:8000]}"
    )

    try:
        response = requests.post(
            f"{OLLAMA_URL}/v1/completions",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "max_tokens": 300,
                "temperature": 0.3,
            },
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()
        text = content.get("choices", [])[0].get("text", "") if isinstance(content.get("choices"), list) else content.get("output", "")
    except Exception:
        return fallback_segments(segments)

    highlights = parse_highlight_output(text)
    if highlights:
        return highlights
    return fallback_segments(segments)


def parse_highlight_output(output: str) -> List[Dict[str, float]]:
    try:
        json_candidates = re.search(r"\[(\{.*\})\]", output, re.DOTALL)
        if json_candidates:
            candidate = output[json_candidates.start():json_candidates.end()]
            return eval(candidate)
    except Exception:
        pass

    timestamps = []
    for line in output.splitlines():
        match = re.search(r"(\d+(?:\.\d+)?)\s*[-–:]\s*(\d+(?:\.\d+)?)", line)
        if match:
            timestamps.append({"start": float(match.group(1)), "end": float(match.group(2)), "label": "highlight"})
    return timestamps


def fallback_segments(segments: List[dict]) -> List[Dict[str, float]]:
    if not segments:
        return [{"start": 0.0, "end": 20.0, "label": "default"}]

    candidate = segments[0]
    return [{"start": float(candidate.get("start", 0.0)), "end": float(min(candidate.get("start", 0.0) + 25.0, candidate.get("end", candidate.get("start", 0.0) + 25.0))), "label": "fallback"}]
