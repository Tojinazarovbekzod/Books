import json
from pathlib import Path
from typing import Dict, Any

DB_PATH = Path(__file__).resolve().parent / "users.json"


def load_users() -> Dict[str, Any]:
    if not DB_PATH.exists():
        return {}

    try:
        with DB_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_users(data: Dict[str, Any]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DB_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
