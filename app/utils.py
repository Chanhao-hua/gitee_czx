import re
from datetime import datetime, timezone

from .config import NAME_ALIASES


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", name or "").lower()
    return NAME_ALIASES.get(cleaned, cleaned)
