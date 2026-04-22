import eventlet
eventlet.monkey_patch()

import os
import re
import jwt
import bcrypt
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, emit

from database import init_db, get_conn

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not set")

JWT_ALGO = "HS256"
PORT = int(os.getenv("PORT", 5001))

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://salarite-frontend-ultw.onrender.com",
]

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(frontend_url)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

CORS(
    app,
    resources={r"/api/*": {"origins": ALLOWED_ORIGINS}},
    supports_credentials=True
)


@app.after_request
def after_request(response):
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Vary"] = "Origin"
    if request.method == "OPTIONS":
        response.status_code = 200
    return response


socketio = SocketIO(
    app,
    cors_allowed_origins=ALLOWED_ORIGINS,
    async_mode="eventlet"
)


def make_token(user):
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGO)


def auth_required(roles=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify({"error": "Missing token"}), 401
            try:
                payload = jwt.decode(header[7:], SECRET_KEY, algorithms=[JWT_ALGO])
                payload["sub"] = int(payload["sub"])
            except (jwt.PyJWTError, ValueError, TypeError):
                return jsonify({"error": "Invalid token"}), 401
            if roles and payload.get("role") not in roles:
                return jsonify({"error": "Forbidden"}), 403
            request.user = payload
            return fn(*args, **kwargs)
        return wrapper
    return deco


def log_activity(type_, message, user_id=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO activities(type,message,user_id) VALUES(%s,%s,%s)",
        (type_, message, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    socketio.emit("activity_new", {"type": type_, "message": message})


@app.route("/api/auth/signup", methods=["POST", "OPTIONS"])
def signup():
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        raw_role = data.get("role")
        if isinstance(raw_role, dict):
            role = (raw_role.get("value") or "").strip().lower()
        else:
            role = str(raw_role or "").strip().lower()

        if not (name and email and password and role in ("employer", "hr", "candidate")):
            return jsonify({"error": "Invalid fields"}), 400

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,%s) RETURNING id",
                (name, email, pw_hash, role),
            )
            user_id = cur.fetchone()["id"]
            conn.commit()

            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            user = cur.fetchone()
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            if "unique" in str(e).lower():
                return jsonify({"error": "Email already used"}), 400
            raise e

        cur.close()
        conn.close()

        user_d = dict(user)
        token = make_token(user_d)

        return jsonify({
            "token": token,
            "user": {
                "id": user_d["id"],
                "name": user_d["name"],
                "email": user_d["email"],
                "role": user_d["role"],
            }
        })

    except Exception as e:
        print("SIGNUP ERROR:", repr(e))
        return jsonify({"error": str(e)}), 500


@app.route("/api/auth/login", methods=["POST", "OPTIONS"])
def login():
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            ok = bcrypt.checkpw(password.encode(), user["password_hash"].encode())
        else:
            ok = False

        if not user or not ok:
            return jsonify({"error": "Invalid credentials"}), 401

        user_d = dict(user)
        token = make_token(user_d)

        return jsonify({
            "token": token,
            "user": {
                "id": user_d["id"],
                "name": user_d["name"],
                "email": user_d["email"],
                "role": user_d["role"],
            }
        })
    except Exception as e:
        print("LOGIN ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.get("/api/auth/me")
@auth_required()
def me():
    return jsonify({
        "user": {
            "id": request.user["sub"],
            "name": request.user["name"],
            "email": request.user["email"],
            "role": request.user["role"],
        }
    })


@app.get("/api/tasks")
@auth_required()
def list_tasks():
    conn = get_conn()
    cur = conn.cursor()

    if request.user["role"] == "employer":
        cur.execute("""
            SELECT t.*, u.name AS employer_name, h.name AS assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.employer_id
            LEFT JOIN users h ON h.id = t.assigned_to
            WHERE t.employer_id = %s
            ORDER BY t.created_at DESC
        """, (request.user["sub"],))
    else:
        cur.execute("""
            SELECT t.*, u.name AS employer_name, h.name AS assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.employer_id
            LEFT JOIN users h ON h.id = t.assigned_to
            WHERE t.assigned_to = %s
            ORDER BY t.created_at DESC
        """, (request.user["sub"],))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.post("/api/tasks")
@auth_required(roles=["employer"])
def create_task():
    data = request.get_json() or {}

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    priority = (data.get("priority") or "medium").strip().lower()
    assigned_hr_email = (data.get("assigned_hr_email") or "").strip().lower()

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not assigned_hr_email:
        return jsonify({"error": "Assignee required"}), 400
    if priority not in ("low", "medium", "high"):
        priority = "medium"

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name, email, role FROM users WHERE lower(email)=%s",
        (assigned_hr_email,)
    )
    hr_user = cur.fetchone()

    if not hr_user:
        cur.close()
        conn.close()
        return jsonify({"error": "HR not found with this email"}), 400

    if hr_user["role"] != "hr":
        cur.close()
        conn.close()
        return jsonify({"error": "Selected user is not an HR"}), 400

    cur.execute(
        """
        INSERT INTO tasks (title, description, priority, status, employer_id, assigned_to)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (title, description, priority, "pending", request.user["sub"], hr_user["id"]),
    )
    task_id = cur.fetchone()["id"]
    conn.commit()

    cur.execute("""
        SELECT t.*, u.name AS employer_name, h.name AS assignee_name, h.email AS assignee_email
        FROM tasks t
        LEFT JOIN users u ON u.id = t.employer_id
        LEFT JOIN users h ON h.id = t.assigned_to
        WHERE t.id = %s
    """, (task_id,))
    task = cur.fetchone()
    cur.close()
    conn.close()

    log_activity(
        "task_created",
        f'Task created: "{title}" assigned to {hr_user["email"]}',
        request.user["sub"],
    )
    socketio.emit("tasks_changed", {})
    return jsonify(dict(task)), 201


@app.get("/api/users")
@auth_required(roles=["employer", "hr"])
def list_users():
    role = request.args.get("role")
    conn = get_conn()
    cur = conn.cursor()

    if role:
        cur.execute(
            "SELECT id, name, email, role FROM users WHERE role=%s ORDER BY name ASC",
            (role,)
        )
    else:
        cur.execute("SELECT id, name, email, role FROM users ORDER BY name ASC")

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.patch("/api/tasks/<int:task_id>")
@auth_required(roles=["employer", "hr"])
def update_task(task_id):
    data = request.get_json() or {}
    status = data.get("status")

    if status not in ("pending", "in_progress", "completed"):
        return jsonify({"error": "Invalid status"}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=%s", (task_id,))
    task = cur.fetchone()

    if not task:
        cur.close()
        conn.close()
        return jsonify({"error": "Not found"}), 404

    if request.user["role"] == "hr":
        if task["assigned_to"] != request.user["sub"]:
            cur.close()
            conn.close()
            return jsonify({"error": "Forbidden"}), 403
        if status == "pending":
            cur.close()
            conn.close()
            return jsonify({"error": "Forbidden"}), 403

    elif request.user["role"] == "employer":
        if task["employer_id"] != request.user["sub"]:
            cur.close()
            conn.close()
            return jsonify({"error": "Forbidden"}), 403
        if status in ("in_progress", "completed"):
            cur.close()
            conn.close()
            return jsonify({"error": "Forbidden"}), 403

    fields = ["status=%s"]
    values = [status]

    if request.user["role"] == "hr" and status == "in_progress":
        fields.append("started_at=CURRENT_TIMESTAMP")
    elif request.user["role"] == "hr" and status == "completed":
        fields.append("completed_at=CURRENT_TIMESTAMP")

    if request.user["role"] == "employer" and status == "pending":
        fields.append("started_at=NULL")
        fields.append("completed_at=NULL")

    values.append(task_id)

    cur.execute(
        f"UPDATE tasks SET {', '.join(fields)} WHERE id=%s",
        values
    )
    conn.commit()

    cur.execute("SELECT * FROM tasks WHERE id=%s", (task_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    msg = {
        "in_progress": f'Task started: "{task["title"]}"',
        "completed": f'Task completed: "{task["title"]}"',
        "pending": f'Task reset: "{task["title"]}"',
    }[status]

    log_activity(f"task_{status}", msg, request.user["sub"])
    socketio.emit("tasks_changed", {})
    return jsonify(dict(row))


@app.get("/api/interviews")
@auth_required()
def list_interviews():
    conn = get_conn()
    cur = conn.cursor()

    if request.user["role"] == "hr":
        cur.execute(
            "SELECT * FROM interviews WHERE created_by=%s ORDER BY scheduled_at ASC",
            (request.user["sub"],)
        )
    else:
        cur.execute(
            "SELECT * FROM interviews WHERE candidate_email=%s ORDER BY scheduled_at ASC",
            (request.user["email"].lower(),)
        )

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.post("/api/interviews")
@auth_required(roles=["hr"])
def create_interview():
    data = request.get_json() or {}

    candidate_name = (data.get("candidate_name") or "").strip()
    candidate_email = (data.get("candidate_email") or "").strip().lower()
    scheduled_at = data.get("scheduled_at")
    mode = data.get("mode") or "video"
    notes = (data.get("notes") or "").strip()

    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not candidate_email or not scheduled_at or mode not in ("voice", "video", "chat"):
        return jsonify({"error": "Invalid fields"}), 400
    if not re.fullmatch(email_pattern, candidate_email):
        return jsonify({"error": "Invalid email address"}), 400
    if candidate_email == request.user["email"].lower():
        return jsonify({"error": "You cannot schedule an interview for your own email"}), 400

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, role FROM users WHERE lower(email)=%s",
        (candidate_email,)
    )
    existing_user = cur.fetchone()

    if existing_user and existing_user["role"] == "hr":
        cur.close()
        conn.close()
        return jsonify({"error": "This email belongs to an HR account"}), 400

    room_id = uuid.uuid4().hex[:12]

    cur.execute(
        """
        INSERT INTO interviews(candidate_name, candidate_email, scheduled_at, mode, room_id, notes, created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        (candidate_name, candidate_email, scheduled_at, mode, room_id, notes, request.user["sub"]),
    )
    interview_id = cur.fetchone()["id"]
    conn.commit()

    cur.execute("SELECT * FROM interviews WHERE id=%s", (interview_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    display_name = candidate_name if candidate_name else candidate_email
    log_activity("interview_scheduled", f'Interview scheduled with {display_name}', request.user["sub"])
    socketio.emit("interviews_changed", {})
    return jsonify(dict(row))


@app.get("/api/interviews/<room_id>/access")
@auth_required()
def interview_access(room_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM interviews WHERE room_id=%s", (room_id,))
    interview = cur.fetchone()
    cur.close()
    conn.close()

    if not interview:
        return jsonify({"error": "Not found"}), 404

    allowed = (
        (request.user["role"] == "hr" and interview["created_by"] == request.user["sub"]) or
        (request.user["email"].lower() == (interview["candidate_email"] or "").lower())
    )

    if not allowed:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify({"ok": True, "interview": dict(interview)})


@app.get("/api/activities")
@auth_required()
def list_activities():
    conn = get_conn()
    cur = conn.cursor()

    if request.user["role"] == "hr":
        cur.execute(
            "SELECT * FROM activities WHERE user_id=%s ORDER BY created_at DESC LIMIT 50",
            (request.user["sub"],)
        )
    else:
        cur.execute("SELECT * FROM activities ORDER BY created_at DESC LIMIT 50")

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([dict(r) for r in rows])


@socketio.on("connect")
def on_connect():
    print(f"Client connected: {request.sid}")


@socketio.on("disconnect")
def on_disconnect():
    print(f"Client disconnected: {request.sid}")


@socketio.on("join_room")
def on_join(data):
    room = data.get("room")
    user = data.get("user", "Guest")
    token = data.get("token")

    if not room:
        emit("room_error", {"error": "Missing room"})
        return

    current_user = None
    if token:
        try:
            current_user = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
            current_user["sub"] = int(current_user["sub"])
        except (jwt.PyJWTError, ValueError, TypeError):
            emit("room_error", {"error": "Invalid token"})
            return

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM interviews WHERE room_id=%s", (room,))
    interview = cur.fetchone()
    cur.close()
    conn.close()

    if interview:
        allowed = current_user and (
            (current_user["role"] == "hr" and interview["created_by"] == current_user["sub"]) or
            (current_user["email"].lower() == (interview["candidate_email"] or "").lower())
        )
        if not allowed:
            emit("room_error", {"error": "Forbidden"})
            return

    join_room(room)
    emit("peer_joined", {"user": user, "sid": request.sid}, to=room, include_self=False)


@socketio.on("leave_room")
def on_leave(data):
    room = data.get("room")
    if room:
        leave_room(room)
        emit("peer_left", {"sid": request.sid}, to=room)


@socketio.on("webrtc_offer")
def on_offer(data):
    emit("webrtc_offer", data, to=data.get("room"), include_self=False)


@socketio.on("webrtc_answer")
def on_answer(data):
    emit("webrtc_answer", data, to=data.get("room"), include_self=False)


@socketio.on("webrtc_ice")
def on_ice(data):
    emit("webrtc_ice", data, to=data.get("room"), include_self=False)


@socketio.on("chat_message")
def on_chat(data):
    emit("chat_message", data, to=data.get("room"), include_self=False)


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


try:
    init_db()
    print("DB initialized successfully")
except Exception as e:
    print(f"DB init error: {e}")


if __name__ == "__main__":
    print(f"Salarite backend running on http://localhost:{PORT}")
    socketio.run(app, host="0.0.0.0", port=PORT, debug=True, use_reloader=False)