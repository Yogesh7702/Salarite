import re
import jwt
import bcrypt
import uuid
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, emit

from database import init_db, get_conn


SECRET_KEY = "salarite-dev-secret-change-me-please-use-32+chars-in-production"
JWT_ALGO = "HS256"
FRONTEND_URL = "http://localhost:5173"
PORT = 5001


app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

CORS(
    app,
    resources={r"/api/*": {"origins": FRONTEND_URL}},
    supports_credentials=True
)

@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = FRONTEND_URL
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    return response

socketio = SocketIO(
    app,
    cors_allowed_origins=[FRONTEND_URL],
    async_mode="threading"
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
    conn.execute(
        "INSERT INTO activities(type,message,user_id) VALUES(?,?,?)",
        (type_, message, user_id),
    )
    conn.commit()
    conn.close()
    socketio.emit("activity_new", {"type": type_, "message": message})


def get_request_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(header[7:], SECRET_KEY, algorithms=[JWT_ALGO])
        payload["sub"] = int(payload["sub"])
        return payload
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


@app.post("/api/auth/signup")
def signup():
    try:
        data = request.get_json() or {}
        print("SIGNUP DATA:", data)

        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        raw_role = data.get("role")

        if isinstance(raw_role, dict):
            role = (raw_role.get("value") or "").strip().lower()
        else:
            role = str(raw_role or "").strip().lower()

        print("PARSED ROLE:", role)

        if not (name and email and password and role in ("employer", "hr", "candidate")):
            return jsonify({"error": "Invalid fields"}), 400

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                (name, email, pw_hash, role),
            )
            conn.commit()

            user = conn.execute(
                "SELECT * FROM users WHERE id=?",
                (cur.lastrowid,)
            ).fetchone()
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({"error": "Email already used"}), 400

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



@app.post("/api/auth/login")
def login():
    try:
        data = request.get_json() or {}

        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        print("LOGIN TRY:", email)

        conn = get_conn()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()
        conn.close()

        print("USER FOUND:", bool(user))

        if user:
            ok = bcrypt.checkpw(password.encode(), user["password_hash"].encode())
            print("PASSWORD MATCH:", ok)
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

    if request.user["role"] == "employer":
        rows = conn.execute("""
            SELECT t.*, u.name AS employer_name, h.name AS assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.employer_id
            LEFT JOIN users h ON h.id = t.assigned_to
            WHERE t.employer_id = ?
            ORDER BY t.created_at DESC
        """, (request.user["sub"],)).fetchall()
    else:
        rows = conn.execute("""
            SELECT t.*, u.name AS employer_name, h.name AS assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.employer_id
            LEFT JOIN users h ON h.id = t.assigned_to
            WHERE t.assigned_to = ?
            ORDER BY t.created_at DESC
        """, (request.user["sub"],)).fetchall()

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

    hr_user = conn.execute(
        "SELECT id, name, email, role FROM users WHERE lower(email)=?",
        (assigned_hr_email,)
    ).fetchone()

    if not hr_user:
        conn.close()
        return jsonify({"error": "HR not found with this email"}), 400

    if hr_user["role"] != "hr":
        conn.close()
        return jsonify({"error": "Selected user is not an HR"}), 400

    cur = conn.execute(
        """
        INSERT INTO tasks (title, description, priority, status, employer_id, assigned_to)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            description,
            priority,
            "pending",
            request.user["sub"],
            hr_user["id"],
        ),
    )
    conn.commit()

    task = conn.execute(
        """
        SELECT t.*,
               u.name AS employer_name,
               h.name AS assignee_name,
               h.email AS assignee_email
        FROM tasks t
        LEFT JOIN users u ON u.id = t.employer_id
        LEFT JOIN users h ON h.id = t.assigned_to
        WHERE t.id = ?
        """,
        (cur.lastrowid,),
    ).fetchone()

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

    if role:
        rows = conn.execute(
            "SELECT id, name, email, role FROM users WHERE role=? ORDER BY name ASC",
            (role,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, email, role FROM users ORDER BY name ASC"
        ).fetchall()

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
    task = conn.execute(
        "SELECT * FROM tasks WHERE id=?",
        (task_id,)
    ).fetchone()

    if not task:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    if request.user["role"] == "hr":
        if task["assigned_to"] != request.user["sub"]:
            conn.close()
            return jsonify({"error": "Forbidden"}), 403

        if status == "pending":
            conn.close()
            return jsonify({"error": "Forbidden"}), 403

    elif request.user["role"] == "employer":
        if task["employer_id"] != request.user["sub"]:
            conn.close()
            return jsonify({"error": "Forbidden"}), 403

        if status in ("in_progress", "completed"):
            conn.close()
            return jsonify({"error": "Forbidden"}), 403

    fields = ["status=?"]
    values = [status]

    if request.user["role"] == "hr" and status == "in_progress":
        fields.append("started_at=CURRENT_TIMESTAMP")
    elif request.user["role"] == "hr" and status == "completed":
        fields.append("completed_at=CURRENT_TIMESTAMP")

    if request.user["role"] == "employer" and status == "pending":
        fields.append("started_at=NULL")
        fields.append("completed_at=NULL")

    values.append(task_id)

    conn.execute(
        f"UPDATE tasks SET {', '.join(fields)} WHERE id=?",
        values
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM tasks WHERE id=?",
        (task_id,)
    ).fetchone()
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

    if request.user["role"] == "hr":
        rows = conn.execute(
            "SELECT * FROM interviews WHERE created_by=? ORDER BY scheduled_at ASC",
            (request.user["sub"],)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM interviews WHERE candidate_email=? ORDER BY scheduled_at ASC",
            (request.user["email"].lower(),)
        ).fetchall()

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

    existing_user = conn.execute(
        "SELECT id, role FROM users WHERE lower(email)=?",
        (candidate_email,)
    ).fetchone()

    if existing_user and existing_user["role"] == "hr":
        conn.close()
        return jsonify({"error": "This email belongs to an HR account"}), 400

    room_id = uuid.uuid4().hex[:12]

    cur = conn.execute(
        """
        INSERT INTO interviews(candidate_name, candidate_email, scheduled_at, mode, room_id, notes, created_by)
        VALUES(?,?,?,?,?,?,?)
        """,
        (candidate_name, candidate_email, scheduled_at, mode, room_id, notes, request.user["sub"]),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM interviews WHERE id=?",
        (cur.lastrowid,)
    ).fetchone()
    conn.close()

    display_name = candidate_name if candidate_name else candidate_email

    log_activity(
        "interview_scheduled",
        f'Interview scheduled with {display_name}',
        request.user["sub"]
    )
    socketio.emit("interviews_changed", {})

    return jsonify(dict(row))


@app.get("/api/interviews/<room_id>/access")
@auth_required()
def interview_access(room_id):
    conn = get_conn()
    interview = conn.execute(
        "SELECT * FROM interviews WHERE room_id=?",
        (room_id,)
    ).fetchone()
    conn.close()

    if not interview:
        return jsonify({"error": "Not found"}), 404

    allowed = (
        (request.user["role"] == "hr" and interview["created_by"] == request.user["sub"]) or
        (request.user["email"].lower() == (interview["candidate_email"] or "").lower())
    )

    if not allowed:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify({
        "ok": True,
        "interview": dict(interview)
    })


@app.get("/api/activities")
@auth_required()
def list_activities():
    conn = get_conn()

    if request.user["role"] == "hr":
        rows = conn.execute(
            """
            SELECT * FROM activities
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (request.user["sub"],)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM activities ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

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
    interview = conn.execute(
        "SELECT * FROM interviews WHERE room_id=?",
        (room,)
    ).fetchone()
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
    print(f"[room {room}] {user} joined")


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


if __name__ == "__main__":
    init_db()
    print(f"Salarite backend running on http://localhost:{PORT}")
    socketio.run(app, host="0.0.0.0", port=PORT, debug=True, use_reloader=False)