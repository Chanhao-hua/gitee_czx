from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.config import CLEANED_DATA_DIR, DEFAULT_TARGET_RECORDS, RAW_DATA_DIR


def parse_limit(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--limit", type=int, default=DEFAULT_TARGET_RECORDS, help="target record count")
    return parser.parse_args()


def write_dataset(name: str, raw_records: list[dict], cleaned_records: list[dict], started_at: float) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DATA_DIR / f"{name}.json"
    cleaned_path = CLEANED_DATA_DIR / f"{name}.json"
    _write_json(raw_path, raw_records)
    _write_json(cleaned_path, cleaned_records)
    elapsed = time.perf_counter() - started_at
    print(
        f"{name}: raw={len(raw_records)} cleaned={len(cleaned_records)} "
        f"elapsed={elapsed:.2f}s cleaned_file={cleaned_path}"
    )


def _write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
