# models.py
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"

@dataclass
class Meeting:
    meetingId: str
    subject: str
    organizerId: str
    organizerName: str
    startDateUTC: str
    endDateUTC: str
    creationDateUTC: str
    isPrivate: bool
    isCancelled: bool

def now_iso_z():
    return datetime.now(tz=timezone.utc).strftime(ISO_FMT)

def meeting_to_dict(meeting: Meeting):
    # ensure no nulls (strings -> "" if None). Booleans must be bool.
    d = asdict(meeting)
    for k,v in d.items():
        if v is None and k != "imageUrl":  # you allowed imageUrl null in original rules
            d[k] = "" if isinstance(v, (str, type(None))) else v
    return d
