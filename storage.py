# storage.py
import os, json, threading, traceback
from models import Meeting

_lock = threading.RLock()
_meetings_by_room = {}

# Persistent location (survives restarts/redeploys on App Service Linux)
DATA_PATH = os.getenv("MEETINGS_PATH", "/home/data/meetings.json")
BUNDLED_PATH = os.path.join(os.path.dirname(__file__), "meetings.json")

def _ensure_dir(path):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        print("[storage] could not create dir:", os.path.dirname(path))
        print(traceback.format_exc())

def _persist():
    """Write all meetings to disk as a flat list with roomId."""
    try:
        _ensure_dir(DATA_PATH)
        flat = []
        for room_id, meetings in _meetings_by_room.items():
            for m in meetings:
                d = m.__dict__.copy()
                d["roomId"] = room_id
                flat.append(d)
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(flat, f, ensure_ascii=False, indent=2)
        print(f"[storage] persisted {len(flat)} meetings to {DATA_PATH}")
    except Exception:
        print("[storage] persist failed")
        print(traceback.format_exc())

def load_meetings():
    """Load from persistent file if present; else from bundled JSON; else empty."""
    global _meetings_by_room
    _meetings_by_room = {}
    source = DATA_PATH if os.path.exists(DATA_PATH) else BUNDLED_PATH
    try:
        if os.path.exists(source):
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"[storage] loading from {source} (items={len(data)})")
        else:
            print("[storage] no meetings file found; starting empty")
            data = []
        for m in data:
            room_id = m.get("roomId", "Room 1")
            meeting = Meeting(
                meetingId=m["meetingId"],
                subject=m.get("subject",""),
                organizerId=m.get("organizerId",""),
                organizerName=m.get("organizerName",""),
                startDateUTC=m["startDateUTC"],
                endDateUTC=m["endDateUTC"],
                creationDateUTC=m.get("creationDateUTC",""),
                isPrivate=bool(m.get("isPrivate", False)),
                isCancelled=bool(m.get("isCancelled", False)),
            )
            _meetings_by_room.setdefault(room_id, []).append(meeting)
        print(f"[storage] rooms loaded: {list(_meetings_by_room.keys())}")
    except Exception:
        print(f"[storage] load failed from {source}, starting empty")
        print(traceback.format_exc())
        _meetings_by_room = {}

def get_meetings(room_id):
    with _lock:
        return list(_meetings_by_room.get(room_id, []))

def add_meeting(room_id, meeting: Meeting):
    with _lock:
        _meetings_by_room.setdefault(room_id, []).append(meeting)
        _persist()

def update_meeting(room_id, meeting_id, fields: dict):
    with _lock:
        arr = _meetings_by_room.get(room_id, [])
        for m in arr:
            if m.meetingId == meeting_id:
                for k, v in fields.items():
                    if hasattr(m, k):
                        setattr(m, k, v)
                _persist()
                return m
        return None

# Initialize on import
load_meetings()
