from pathlib import Path

BASE_DATA_PATH = Path("/app/data")
RAW_DIR = BASE_DATA_PATH / "raw"
WORK_DIR = BASE_DATA_PATH / "temp"
OUTPUT_DIR = BASE_DATA_PATH / "output"


def ensure_data_directories() -> None:
    for path in [BASE_DATA_PATH, RAW_DIR, WORK_DIR, OUTPUT_DIR]:
        path.mkdir(parents=True, exist_ok=True)
