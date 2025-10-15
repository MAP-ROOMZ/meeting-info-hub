# storage.py
import os, json, threading
from models import Meeting

_lock = threading.RLock()
_meetings_by_room = {}

# where to store data (persistent on App Service Linux)
# /home is persistent across restarts; /home/data survives redeploys too.
DATA_PATH = os.getenv("MEETINGS_PATH", "/home/data/meetings.json")

def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _persist():
    """Write all meetings to disk as a flat list with roomId."""
    _ensure_dir(DATA_PATH)
    flat = []
    for room_id, meetings in _meetings_by_room.items():
        for m in meetings:
            d = m.__dict__.copy()
            d["roomId"] = room_id
            flat.append(d)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2)

def load_meetings():
    """Load from persistent file if it exists; else from bundled meetings.json."""
    global _meetings_by_room
    _meetings_by_room = {}
    source = DATA_PATH if os.path.exists(DATA_PATH) else os.path.join(os.path.dirname(__file__), "meetings.json")
    try:
        with open(source, "r", encoding="utf-8") as f:
            data = json.load(f)
        for m in data:
            room_id = m.get("roomId", "Room 1")
            meeting = Meeting(
                meetingId=m["meetingId"],
                subject=m["subject"],
                organizerId=m.get("organizerId", ""),
                organizerName=m.get("organizerName", ""),
                startDateUTC=m["startDateUTC"],
                endDateUTC=m["endDateUTC"],
                creationDateUTC=m.get("creationDateUTC", ""),
                isPrivate=bool(m.get("isPrivate", False)),
                isCancelled=bool(m.get("isCancelled", False)),
            )
            _meetings_by_room.setdefault(room_id, []).append(meeting)
    except Exception:
        _meetings_by_room = {}

def get_meetings(room_id):
    with _lock:
        return list(_meetings_by_room.get(room_id, []))

def add_meeting(room_id, meeting: Meeting):
    with _lock:
        _meetings_by_room.setdefault(room_id, []).append(meeting)
        _persist()  # <-- save

def update_meeting(room_id, meeting_id, fields: dict):
    with _lock:
        arr = _meetings_by_room.get(room_id, [])
        for i, m in enumerate(arr):
            if m.meetingId == meeting_id:
                for k, v in fields.items():
                    if hasattr(m, k):
                        setattr(m, k, v)
                _persist()  # <-- save
                return m
        return None

# call once at import
load_meetings()
