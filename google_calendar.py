# google_calendar.py
import os, json, datetime
from typing import List
from googleapiclient.discovery import build
from google.oauth2 import service_account
from models import Meeting

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def _build_client():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON is missing")
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def fetch_meetings(calendar_id: str, time_min_iso: str | None, time_max_iso: str | None) -> List[Meeting]:
    svc = _build_client()

    # Default window: now .. now+lookahead
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    if not time_min_iso:
        time_min_iso = now.isoformat().replace("+00:00", "Z")
    if not time_max_iso:
        hours = int(os.getenv("DEFAULT_LOOKAHEAD_HOURS", "24"))
        time_max_iso = (now + datetime.timedelta(hours=hours)).isoformat().replace("+00:00", "Z")

    events = svc.events().list(
        calendarId=calendar_id,
        timeMin=time_min_iso,
        timeMax=time_max_iso,
        singleEvents=True,
        orderBy="startTime"
    ).execute().get("items", [])

    meetings: List[Meeting] = []
    for e in events:
        # Resolve start/end in UTC ISO
        def _to_iso(v):
            if not v: return None
            # v can be 'dateTime' or all-day 'date'
            dt = v.get("dateTime") or (v.get("date") + "T00:00:00Z")
            # ensure Z suffix
            return dt if dt.endswith("Z") else dt

        subject = e.get("summary") or ""
        organizer_email = (e.get("organizer") or {}).get("email", "")
        organizer_name = (e.get("organizer") or {}).get("displayName") or organizer_email or ""
        meetings.append(Meeting(
            meetingId=e.get("id"),
            subject=subject,
            organizerId=organizer_email,      # use organizer email as ID
            organizerName=organizer_name,
            startDateUTC=_to_iso(e.get("start")),
            endDateUTC=_to_iso(e.get("end")),
            creationDateUTC=(e.get("created") or "").replace(".000Z",".000Z"),
            isPrivate=bool(e.get("privateCopy", False) or e.get("visibility") == "private"),
            isCancelled=(e.get("status") == "cancelled"),
        ))
    return meetings
