import base64

from typing import Any, Dict
from datetime import datetime
from flask import jsonify
from zoneinfo import ZoneInfo

def row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert database row to dictionary with base64 encoded bytes"""
    result: Dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, bytes):
            result[key] = base64.b64encode(value).decode("ascii")
        else:
            result[key] = value
    return result

def ok(data: Any = None, status: int = 200):
    if data is None:
        return ("", status)
    return (jsonify(data), status)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

def now_iso_seconds() -> str:
    return datetime.now(TAIPEI_TZ).replace(microsecond=0).isoformat()

def now_iso_with_tz(tz_name: str = 'Asia/Taipei') -> str:
    try:
        tz = ZoneInfo(tz_name)
        return datetime.now(tz).replace(microsecond=0).isoformat()
    except Exception as e:
        print(f"Warning: Failed to use timezone {tz_name}, falling back to Taipei: {e}")
        return now_iso_seconds()
