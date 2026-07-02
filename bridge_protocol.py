from __future__ import annotations

import json
from typing import Any

from models import CanFrame


def make_request(cmd: str, **kwargs: Any) -> dict[str, Any]:
    return {"cmd": cmd, **kwargs}


def encode_message(message: dict[str, Any]) -> str:
    return json.dumps(message, separators=(",", ":")) + "\n"


def decode_message(line: str) -> dict[str, Any]:
    message = json.loads(line)
    if not isinstance(message, dict):
        raise ValueError("Bridge message must be a JSON object.")
    return message


def frame_to_dict(frame: CanFrame) -> dict[str, Any]:
    return {
        "can_id": frame.can_id,
        "data": frame.data[: frame.dlc].hex(),
        "dlc": frame.dlc,
        "extended": frame.extended,
        "rtr": frame.rtr,
        "timestamp": frame.timestamp,
    }


def frame_from_dict(data: dict[str, Any]) -> CanFrame:
    payload = bytes.fromhex(str(data["data"]))
    dlc = int(data.get("dlc", len(payload)))
    return CanFrame(
        can_id=int(data["can_id"]),
        data=payload[:dlc],
        dlc=dlc,
        extended=bool(data.get("extended", False)),
        rtr=bool(data.get("rtr", False)),
        timestamp=float(data.get("timestamp", 0.0)),
    )
