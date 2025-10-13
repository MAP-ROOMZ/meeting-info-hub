# app.py
import os
import uuid
from functools import wraps
from flask import Flask, jsonify, request, Response, send_file
from dateutil import parser
from models import Meeting, meeting_to_dict, now_iso_z
import storage, io

app = Flask(__name__)

# Optional: allow simple CORS for a wall display (set ENABLE_CORS=1)
if os.getenv("ENABLE_CORS") == "1":
    @app.after_request
    def _add_cors_headers(resp):
        resp.headers["Access-Control-Allow-Origin"] = os.getenv("CORS_ORIGIN", "*")
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,OPTIONS"
        return resp

# Basic Auth (set API_USERNAME and API_PASSWORD in env)
API_USERNAME = os.getenv("Marcel_Test")
API_PASSWORD = os.getenv("Roomz1234$")

def requires_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # If no creds configured, allow open access (useful for local dev)
        if not API_USERNAME and not API_PASSWORD:
            return fn(*args, **kwargs)
        auth = request.authorization
        if not auth or auth.username != API_USERNAME or auth.password != API_PASSWORD:
            return Response(
                "Unauthorized", 401,
                {"WWW-Authenticate": 'Basic realm="Meeting API"'}
            )
        return fn(*args, **kwargs)
    return wrapper

# Simple rooms list
ROOMS = [
    {"roomId": "Room 1", "name": "Meeting Room Bern"},
    {"roomId": "Room 2", "name": "Meeting Room Zurich"}
]

def iso_to_dt(s):
    try:
        return parser.isoparse(s)
    except Exception:
        return None

@app.route("/")
def welcome():
    return "Welcome to the ROOMZ Connector API", 200

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

# GET /rooms
@app.route("/rooms", methods=["GET"])
@requires_auth
def get_rooms():
    return jsonify({"rooms": ROOMS}), 200

# GET /rooms/<roomId>/meetings
# Supports: ?start=ISO&end=ISO&organizerId=org-1
@app.route("/rooms/<room_id>/meetings", methods=["GET"])
@requires_auth
def get_meetings(room_id):
    start_q = request.args.get("start")
    end_q = request.args.get("end")
    organizer_q = request.args.get("organizerId")

    start_dt = iso_to_dt(start_q) if start_q else None
    end_dt = iso_to_dt(end_q) if end_q else None

    items = [meeting_to_dict(m) for m in storage.get_meetings(room_id)]

    # Time window filter (inclusive start, exclusive end)
    def in_window(m):
        if not start_dt and not end_dt:
            return True
        s = iso_to_dt(m["startDateUTC"])
        e = iso_to_dt(m["endDateUTC"])
        if not s or not e:
            return False
        if start_dt and e <= start_dt:
            return False
        if end_dt and s >= end_dt:
            return False
        return True

    # Organizer filter
    if organizer_q:
        items = [m for m in items if (m.get("organizerId") == organizer_q)]

    items = [m for m in items if in_window(m)]

    return jsonify({"count": len(items), "items": items}), 200

# POST /rooms/<roomId>/meetings  -> create a meeting (in-memory)
@app.route("/rooms/<room_id>/meetings", methods=["POST"])
@requires_auth
def create_meeting(room_id):
    data = request.get_json() or {}
    required = ["subject","organizerName","startDateUTC","endDateUTC","creationDateUTC","isPrivate","isCancelled"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields. Required: subject, organizerName, startDateUTC, endDateUTC, creationDateUTC, isPrivate, isCancelled"}), 400

    meeting_id = data.get("meetingId") or f"m-{uuid.uuid4().hex[:8]}"
    meeting = Meeting(
        meetingId=meeting_id,
        subject=data.get("subject",""),
        organizerId=data.get("organizerId",""),
        organizerName=data.get("organizerName",""),
        startDateUTC=data.get("startDateUTC"),
        endDateUTC=data.get("endDateUTC"),
        creationDateUTC=data.get("creationDateUTC") or now_iso_z(),
        isPrivate=bool(data.get("isPrivate", False)),
        isCancelled=bool(data.get("isCancelled", False))
    )
    storage.add_meeting(room_id, meeting)
    return jsonify(meeting_to_dict(meeting)), 201

# PUT /rooms/<roomId>/meetings/<meetingId> -> update existing
@app.route("/rooms/<room_id>/meetings/<meeting_id>", methods=["PUT"])
@requires_auth
def update_meeting(room_id, meeting_id):
    data = request.get_json() or {}
    updated = storage.update_meeting(room_id, meeting_id, data)
    if updated:
        return jsonify(meeting_to_dict(updated)), 200
    return jsonify({"error": "Meeting not found (only meetings created via POST can be updated)"}), 404

@app.route('/favicon.ico')
def favicon():
    # return a 1x1 transparent icon so browser is happy
    empty_icon = io.BytesIO(
        b'\x00\x00\x01\x00\x01\x00\x10\x10\x10\x00\x00\x00\x00\x00\x28\x01\x00\x00'
    )
    return send_file(empty_icon, mimetype='image/x-icon')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
