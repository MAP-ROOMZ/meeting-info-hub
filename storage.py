# storage.py
import json
import threading
from pathlib import Path
from models import Meeting
from typing import List

_LOCK = threading.Lock()
_DATA = {}  # room_id -> list[Meeting]

SEED_PATH = Path("meetings.json")


def _load_seed():
    if not SEED_PATH.exists():
        return
    try:
        j = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        for m in j:
            # assume seed entries already match Meeting fields
            meeting = Meeting(
                meetingId=m.get("meetingId", ""),
                subject=m.get("subject", ""),
                organizerId=m.get("organizerId", ""),
                organizerName=m.get("organizerName", ""),
                startDateUTC=m.get("startDateUTC", ""),
                endDateUTC=m.get("endDateUTC", ""),
                creationDateUTC=m.get("creationDateUTC", ""),
                isPrivate=bool(m.get("isPrivate", False)),
                isCancelled=bool(m.get("isCancelled", False))
            )
            # put them in a default room if not provided
            room_id = m.get("roomId", "Room 1")
            _DATA.setdefault(room_id, []).append(meeting)
    except Exception:
        pass


_load_seed()


def get_meetings(room_id) -> List[Meeting]:
    return list(_DATA.get(room_id, []))


def add_meeting(room_id, meeting: Meeting):
    with _LOCK:
        _DATA.setdefault(room_id, []).append(meeting)


def update_meeting(room_id, meeting_id, updates: dict):
    with _LOCK:
        room = _DATA.get(room_id, [])
        for i, m in enumerate(room):
            if m.meetingId == meeting_id:
                # update allowed fields
                for k, v in updates.items():
                    if hasattr(m, k):
                        setattr(m, k, v)
                room[i] = m
                return m
    return None
