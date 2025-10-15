# app.py
import os, uuid, io
from functools import wraps
from flask import Flask, jsonify, request, Response, send_file
from dateutil import parser
from models import Meeting, meeting_to_dict, now_iso_z
import storage

#test redeploy github

app = Flask(__name__)

# CORS (optional)
if os.getenv("ENABLE_CORS") == "1":
    @app.after_request
    def _add_cors_headers(resp):
        resp.headers["Access-Control-Allow-Origin"] = os.getenv("CORS_ORIGIN", "*")
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,OPTIONS"
        return resp

# ---- Basic Auth (correct names) ----
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")

def requires_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not API_USERNAME and not API_PASSWORD:
            return fn(*args, **kwargs)
        auth = request.authorization
        if not auth or auth.username != API_USERNAME or auth.password != API_PASSWORD:
            return Response("Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Meeting API"'})
        return fn(*args, **kwargs)
    return wrapper

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

@app.route("/rooms", methods=["GET"])
@requires_auth
def get_rooms():
    return jsonify({"rooms": ROOMS}), 200

@app.route("/rooms/<room_id>/meetings", methods=["GET"])
@requires_auth
def get_meetings(room_id):
    start_q = request.args.get("start")
    end_q = request.args.get("end")
    organizer_q = request.args.get("organizerId")
    start_dt = iso_to_dt(start_q) if start_q else None
    end_dt = iso_to_dt(end_q) if end_q else None

    items = [meeting_to_dict(m) for m in storage.get_meetings(room_id)]

    def in_window(m):
        if not start_dt and not end_dt:
            return True
        s = iso_to_dt(m["startDateUTC"]); e = iso_to_dt(m["endDateUTC"])
        if not s or not e: return False
        if start_dt and e <= start_dt: return False
        if end_dt and s >= end_dt: return False
        return True

    if organizer_q:
        items = [m for m in items if m.get("organizerId") == organizer_q]
    items = [m for m in items if in_window(m)]
    return jsonify(items), 200

@app.route("/rooms/<room_id>/meetings", methods=["POST"])
@requires_auth
def create_meeting(room_id):
    data = request.get_json() or {}
    required = ["subject","organizerName","startDateUTC","endDateUTC","creationDateUTC","isPrivate","isCancelled"]
    if not all(k in data for k in required):
        return jsonify({"error":"Missing required fields"}), 400
    meeting = Meeting(
        meetingId=data.get("meetingId") or f"m-{uuid.uuid4().hex[:8]}",
        subject=data.get("subject",""),
        organizerId=data.get("organizerId",""),
        organizerName=data.get("organizerName",""),
        startDateUTC=data.get("startDateUTC"),
        endDateUTC=data.get("endDateUTC"),
        creationDateUTC=data.get("creationDateUTC") or now_iso_z(),
        isPrivate=bool(data.get("isPrivate", False)),
        isCancelled=bool(data.get("isCancelled", False)),
    )
    storage.add_meeting(room_id, meeting)
    return jsonify(meeting_to_dict(meeting)), 201

@app.route("/rooms/<room_id>/meetings/<meeting_id>", methods=["PUT"])
@requires_auth
def update_meeting(room_id, meeting_id):
    data = request.get_json() or {}
    updated = storage.update_meeting(room_id, meeting_id, data)
    if updated: return jsonify(meeting_to_dict(updated)), 200
    return jsonify({"error": "Meeting not found"}), 404

@app.route("/favicon.ico")
def favicon():
    return send_file(io.BytesIO(b'\x00\x00\x01\x00\x01\x00\x10\x10\x10\x00\x00\x00\x00\x00\x28\x01\x00\x00'),
                     mimetype='image/x-icon')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")), debug=True)


