import os
import re
import jwt
import bcrypt
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import socketio

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


# --- App Setup ---

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=ALLOWED_ORIGINS)

app = FastAPI(title="Salarite API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# --- Request Models ---

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"
    assigned_hr_email: str

class TaskUpdateRequest(BaseModel):
    status: str

class InterviewCreateRequest(BaseModel):
    candidate_name: Optional[str] = ""
    candidate_email: str
    scheduled_at: str
    mode: Optional[str] = "video"
    notes: Optional[str] = ""


# --- Auth Helpers ---

security = HTTPBearer()

def make_token(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGO)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[JWT_ALGO])
        payload["sub"] = int(payload["sub"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*roles):
    def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return checker


def log_activity(type_: str, message: str, user_id: int = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO activities(type,message,user_id) VALUES(%s,%s,%s)",
        (type_, message, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


# --- Auth Routes ---

@app.post("/api/auth/signup", tags=["Auth"])
def signup(body: SignupRequest):
    name = body.name.strip()
    email = body.email.strip().lower()
    password = body.password
    role = body.role.strip().lower() if isinstance(body.role, str) else ""

    if not (name and email and password and role in ("employer", "hr", "candidate")):
        raise HTTPException(status_code=400, detail="Invalid fields")

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
        user = dict(cur.fetchone())
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        if "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="Email already used")
        raise HTTPException(status_code=500, detail=str(e))

    cur.close()
    conn.close()

    return {
        "token": make_token(user),
        "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
    }


@app.post("/api/auth/login", tags=["Auth"])
def login(body: LoginRequest):
    email = body.email.strip().lower()
    password = body.password

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_d = dict(user)
    return {
        "token": make_token(user_d),
        "user": {"id": user_d["id"], "name": user_d["name"], "email": user_d["email"], "role": user_d["role"]}
    }


@app.get("/api/auth/me", tags=["Auth"])
def me(user: dict = Depends(get_current_user)):
    return {"user": {"id": user["sub"], "name": user["name"], "email": user["email"], "role": user["role"]}}


# --- Task Routes ---

@app.get("/api/tasks", tags=["Tasks"])
def list_tasks(user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    if user["role"] == "employer":
        cur.execute("""
            SELECT t.*, u.name AS employer_name, h.name AS assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.employer_id
            LEFT JOIN users h ON h.id = t.assigned_to
            WHERE t.employer_id = %s ORDER BY t.created_at DESC
        """, (user["sub"],))
    else:
        cur.execute("""
            SELECT t.*, u.name AS employer_name, h.name AS assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.employer_id
            LEFT JOIN users h ON h.id = t.assigned_to
            WHERE t.assigned_to = %s ORDER BY t.created_at DESC
        """, (user["sub"],))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/tasks", status_code=201, tags=["Tasks"])
def create_task(body: TaskCreateRequest, user: dict = Depends(require_roles("employer"))):
    title = body.title.strip()
    description = (body.description or "").strip()
    priority = (body.priority or "medium").strip().lower()
    assigned_hr_email = body.assigned_hr_email.strip().lower()

    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not assigned_hr_email:
        raise HTTPException(status_code=400, detail="Assignee required")
    if priority not in ("low", "medium", "high"):
        priority = "medium"

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, name, email, role FROM users WHERE lower(email)=%s", (assigned_hr_email,))
    hr_user = cur.fetchone()

    if not hr_user:
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="HR not found with this email")
    if hr_user["role"] != "hr":
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="Selected user is not an HR")

    cur.execute(
        "INSERT INTO tasks (title,description,priority,status,employer_id,assigned_to) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
        (title, description, priority, "pending", user["sub"], hr_user["id"]),
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
    task = dict(cur.fetchone())
    cur.close()
    conn.close()

    log_activity("task_created", f'Task created: "{title}" assigned to {hr_user["email"]}', user["sub"])
    return task


@app.patch("/api/tasks/{task_id}", tags=["Tasks"])
def update_task(task_id: int, body: TaskUpdateRequest, user: dict = Depends(require_roles("employer", "hr"))):
    status = body.status

    if status not in ("pending", "in_progress", "completed"):
        raise HTTPException(status_code=400, detail="Invalid status")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=%s", (task_id,))
    task = cur.fetchone()

    if not task:
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Not found")

    if user["role"] == "hr":
        if task["assigned_to"] != user["sub"] or status == "pending":
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Forbidden")
    elif user["role"] == "employer":
        if task["employer_id"] != user["sub"] or status in ("in_progress", "completed"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Forbidden")

    fields = ["status=%s"]
    values = [status]

    if user["role"] == "hr" and status == "in_progress":
        fields.append("started_at=CURRENT_TIMESTAMP")
    elif user["role"] == "hr" and status == "completed":
        fields.append("completed_at=CURRENT_TIMESTAMP")
    if user["role"] == "employer" and status == "pending":
        fields.append("started_at=NULL")
        fields.append("completed_at=NULL")

    values.append(task_id)
    cur.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id=%s", values)
    conn.commit()

    cur.execute("SELECT * FROM tasks WHERE id=%s", (task_id,))
    row = dict(cur.fetchone())
    cur.close()
    conn.close()

    msg = {
        "in_progress": f'Task started: "{task["title"]}"',
        "completed": f'Task completed: "{task["title"]}"',
        "pending": f'Task reset: "{task["title"]}"'
    }[status]
    log_activity(f"task_{status}", msg, user["sub"])
    return row


# --- Users ---

@app.get("/api/users", tags=["Users"])
def list_users(role: Optional[str] = None, user: dict = Depends(require_roles("employer", "hr"))):
    conn = get_conn()
    cur = conn.cursor()

    if role:
        cur.execute("SELECT id, name, email, role FROM users WHERE role=%s ORDER BY name ASC", (role,))
    else:
        cur.execute("SELECT id, name, email, role FROM users ORDER BY name ASC")

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


# --- Interview Routes ---

@app.get("/api/interviews", tags=["Interviews"])
def list_interviews(user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    if user["role"] == "hr":
        cur.execute("SELECT * FROM interviews WHERE created_by=%s ORDER BY scheduled_at ASC", (user["sub"],))
    else:
        cur.execute("SELECT * FROM interviews WHERE candidate_email=%s ORDER BY scheduled_at ASC", (user["email"].lower(),))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/interviews", status_code=201, tags=["Interviews"])
def create_interview(body: InterviewCreateRequest, user: dict = Depends(require_roles("hr"))):
    candidate_name = (body.candidate_name or "").strip()
    candidate_email = body.candidate_email.strip().lower()
    scheduled_at = body.scheduled_at
    mode = body.mode or "video"
    notes = (body.notes or "").strip()

    if not candidate_email or not scheduled_at or mode not in ("voice", "video", "chat"):
        raise HTTPException(status_code=400, detail="Invalid fields")
    if not re.fullmatch(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", candidate_email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if candidate_email == user["email"].lower():
        raise HTTPException(status_code=400, detail="You cannot schedule an interview for your own email")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, role FROM users WHERE lower(email)=%s", (candidate_email,))
    existing = cur.fetchone()
    if existing and existing["role"] == "hr":
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="This email belongs to an HR account")

    room_id = uuid.uuid4().hex[:12]

    cur.execute(
        "INSERT INTO interviews(candidate_name,candidate_email,scheduled_at,mode,room_id,notes,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (candidate_name, candidate_email, scheduled_at, mode, room_id, notes, user["sub"]),
    )
    interview_id = cur.fetchone()["id"]
    conn.commit()

    cur.execute("SELECT * FROM interviews WHERE id=%s", (interview_id,))
    row = dict(cur.fetchone())
    cur.close()
    conn.close()

    log_activity("interview_scheduled", f'Interview scheduled with {candidate_name or candidate_email}', user["sub"])
    return row


@app.get("/api/interviews/{room_id}/access", tags=["Interviews"])
def interview_access(room_id: str, user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM interviews WHERE room_id=%s", (room_id,))
    interview = cur.fetchone()
    cur.close()
    conn.close()

    if not interview:
        raise HTTPException(status_code=404, detail="Not found")

    allowed = (
        (user["role"] == "hr" and interview["created_by"] == user["sub"]) or
        (user["email"].lower() == (interview["candidate_email"] or "").lower())
    )

    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden")

    return {"ok": True, "interview": dict(interview)}


# --- Activities ---

@app.get("/api/activities", tags=["Activities"])
def list_activities(user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    if user["role"] == "hr":
        cur.execute("SELECT * FROM activities WHERE user_id=%s ORDER BY created_at DESC LIMIT 50", (user["sub"],))
    else:
        cur.execute("SELECT * FROM activities ORDER BY created_at DESC LIMIT 50")

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


# --- Health ---

@app.get("/api/health", tags=["System"])
def health():
    return {"ok": True}


# --- Socket.IO Events ---

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.event
async def join_room(sid, data):
    room = data.get("room")
    user_name = data.get("user", "Guest")
    token = data.get("token")

    if not room:
        await sio.emit("room_error", {"error": "Missing room"}, to=sid)
        return

    current_user = None
    if token:
        try:
            current_user = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
            current_user["sub"] = int(current_user["sub"])
        except Exception:
            await sio.emit("room_error", {"error": "Invalid token"}, to=sid)
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
            await sio.emit("room_error", {"error": "Forbidden"}, to=sid)
            return

    await sio.enter_room(sid, room)
    await sio.emit("peer_joined", {"user": user_name, "sid": sid}, room=room, skip_sid=sid)

@sio.event
async def leave_room(sid, data):
    room = data.get("room")
    if room:
        await sio.leave_room(sid, room)
        await sio.emit("peer_left", {"sid": sid}, room=room)

@sio.event
async def webrtc_offer(sid, data):
    await sio.emit("webrtc_offer", data, room=data.get("room"), skip_sid=sid)

@sio.event
async def webrtc_answer(sid, data):
    await sio.emit("webrtc_answer", data, room=data.get("room"), skip_sid=sid)

@sio.event
async def webrtc_ice(sid, data):
    await sio.emit("webrtc_ice", data, room=data.get("room"), skip_sid=sid)

@sio.event
async def chat_message(sid, data):
    await sio.emit("chat_message", data, room=data.get("room"), skip_sid=sid)


# --- Startup ---

@app.on_event("startup")
async def startup():
    try:
        init_db()
        print("DB initialized successfully")
    except Exception as e:
        print(f"DB init error: {e}")