import os
import re
import jwt
import bcrypt
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import socketio

from database import init_db, get_conn

# ============================================================================
# CONFIGURATION
# ============================================================================

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

# ============================================================================
# FASTAPI APP + SOCKETIO
# ============================================================================

# Socket.IO server (ASGI compatible)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=ALLOWED_ORIGINS
)

# FastAPI app
app = FastAPI(
    title="Salarite API",
    description="HR Management Platform - Interviews, Tasks, Real-time Calls",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO on /socket.io path
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ============================================================================
# PYDANTIC MODELS (Request/Response schemas)
# ============================================================================

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

# ============================================================================
# JWT HELPERS
# ============================================================================

security = HTTPBearer()

def make_token(user: dict) -> str:
    """User ka JWT token banata hai — 7 din ki expiry ke saath"""
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    """Token decode karta hai — invalid hone par exception raise karta hai"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
        payload["sub"] = int(payload["sub"])
        return payload
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """FastAPI dependency — har protected route mein inject hoti hai.
    Authorization header se token nikalta hai aur verify karta hai."""
    return decode_token(credentials.credentials)


def require_roles(*roles):
    """Role-based access control dependency factory.
    Usage: Depends(require_roles('employer', 'hr'))"""
    def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return checker

# ============================================================================
# ACTIVITY LOGGER
# ============================================================================

def log_activity(type_: str, message: str, user_id: int = None):
    """Activity database mein save karta hai aur real-time broadcast karta hai"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO activities(type,message,user_id) VALUES(%s,%s,%s)",
        (type_, message, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()

# ============================================================================
# AUTH ROUTES
# ============================================================================

@app.post("/api/auth/signup", tags=["Auth"])
def signup(body: SignupRequest):
    """
    Naya user register karna.
    - **name**: Full name
    - **email**: Unique email
    - **password**: Plain text (bcrypt se hash hoga)
    - **role**: employer | hr | candidate
    """
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

    token = make_token(user)
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        }
    }


@app.post("/api/auth/login", tags=["Auth"])
def login(body: LoginRequest):
    """
    User login.
    - **email**: Registered email
    - **password**: Plain text password
    """
    email = body.email.strip().lower()
    password = body.password

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
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_d = dict(user)
    token = make_token(user_d)

    return {
        "token": token,
        "user": {
            "id": user_d["id"],
            "name": user_d["name"],
            "email": user_d["email"],
            "role": user_d["role"],
        }
    }


@app.get("/api/auth/me", tags=["Auth"])
def me(user: dict = Depends(get_current_user)):
    """Current logged-in user ki info return karta hai (token se)"""
    return {
        "user": {
            "id": user["sub"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        }
    }

# ============================================================================
# TASK ROUTES
# ============================================================================

@app.get("/api/tasks", tags=["Tasks"])
def list_tasks(user: dict = Depends(get_current_user)):
    """
    Tasks list karta hai.
    - Employer: apne banaye tasks
    - HR: apne assigned tasks
    """
    conn = get_conn()
    cur = conn.cursor()

    if user["role"] == "employer":
        cur.execute("""
            SELECT t.*, u.name AS employer_name, h.name AS assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.employer_id
            LEFT JOIN users h ON h.id = t.assigned_to
            WHERE t.employer_id = %s
            ORDER BY t.created_at DESC
        """, (user["sub"],))
    else:
        cur.execute("""
            SELECT t.*, u.name AS employer_name, h.name AS assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.employer_id
            LEFT JOIN users h ON h.id = t.assigned_to
            WHERE t.assigned_to = %s
            ORDER BY t.created_at DESC
        """, (user["sub"],))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/tasks", status_code=201, tags=["Tasks"])
def create_task(body: TaskCreateRequest, user: dict = Depends(require_roles("employer"))):
    """
    Naya task create karna (sirf employer).
    HR ki email se assign karta hai.
    """
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

    cur.execute(
        "SELECT id, name, email, role FROM users WHERE lower(email)=%s",
        (assigned_hr_email,)
    )
    hr_user = cur.fetchone()

    if not hr_user:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="HR not found with this email")

    if hr_user["role"] != "hr":
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Selected user is not an HR")

    cur.execute(
        """
        INSERT INTO tasks (title, description, priority, status, employer_id, assigned_to)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """,
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
    """
    Task status update karna.
    - HR: pending → in_progress → completed
    - Employer: kisi bhi task ko pending reset kar sakta hai
    """
    status = body.status

    if status not in ("pending", "in_progress", "completed"):
        raise HTTPException(status_code=400, detail="Invalid status")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=%s", (task_id,))
    task = cur.fetchone()

    if not task:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Not found")

    if user["role"] == "hr":
        if task["assigned_to"] != user["sub"]:
            cur.close()
            conn.close()
            raise HTTPException(status_code=403, detail="Forbidden")
        if status == "pending":
            cur.close()
            conn.close()
            raise HTTPException(status_code=403, detail="Forbidden")

    elif user["role"] == "employer":
        if task["employer_id"] != user["sub"]:
            cur.close()
            conn.close()
            raise HTTPException(status_code=403, detail="Forbidden")
        if status in ("in_progress", "completed"):
            cur.close()
            conn.close()
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
        "pending": f'Task reset: "{task["title"]}"',
    }[status]

    log_activity(f"task_{status}", msg, user["sub"])
    return row

# ============================================================================
# USERS ROUTE
# ============================================================================

@app.get("/api/users", tags=["Users"])
def list_users(role: Optional[str] = None, user: dict = Depends(require_roles("employer", "hr"))):
    """
    Users ki list. Optional ?role=hr se filter kar sakte ho.
    Password hash return nahi hota.
    """
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
    return [dict(r) for r in rows]

# ============================================================================
# INTERVIEW ROUTES
# ============================================================================

@app.get("/api/interviews", tags=["Interviews"])
def list_interviews(user: dict = Depends(get_current_user)):
    """
    Interviews list karta hai.
    - HR: apne schedule kiye
    - Candidate: apne email se linked
    """
    conn = get_conn()
    cur = conn.cursor()

    if user["role"] == "hr":
        cur.execute(
            "SELECT * FROM interviews WHERE created_by=%s ORDER BY scheduled_at ASC",
            (user["sub"],)
        )
    else:
        cur.execute(
            "SELECT * FROM interviews WHERE candidate_email=%s ORDER BY scheduled_at ASC",
            (user["email"].lower(),)
        )

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/interviews", status_code=201, tags=["Interviews"])
def create_interview(body: InterviewCreateRequest, user: dict = Depends(require_roles("hr"))):
    """
    Naya interview schedule karna (sirf HR).
    Unique room_id generate hota hai for video/voice call.
    """
    candidate_name = (body.candidate_name or "").strip()
    candidate_email = body.candidate_email.strip().lower()
    scheduled_at = body.scheduled_at
    mode = body.mode or "video"
    notes = (body.notes or "").strip()

    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not candidate_email or not scheduled_at or mode not in ("voice", "video", "chat"):
        raise HTTPException(status_code=400, detail="Invalid fields")
    if not re.fullmatch(email_pattern, candidate_email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if candidate_email == user["email"].lower():
        raise HTTPException(status_code=400, detail="You cannot schedule an interview for your own email")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, role FROM users WHERE lower(email)=%s", (candidate_email,))
    existing_user = cur.fetchone()

    if existing_user and existing_user["role"] == "hr":
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="This email belongs to an HR account")

    room_id = uuid.uuid4().hex[:12]

    cur.execute(
        """
        INSERT INTO interviews(candidate_name, candidate_email, scheduled_at, mode, room_id, notes, created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        (candidate_name, candidate_email, scheduled_at, mode, room_id, notes, user["sub"]),
    )
    interview_id = cur.fetchone()["id"]
    conn.commit()

    cur.execute("SELECT * FROM interviews WHERE id=%s", (interview_id,))
    row = dict(cur.fetchone())
    cur.close()
    conn.close()

    display_name = candidate_name if candidate_name else candidate_email
    log_activity("interview_scheduled", f'Interview scheduled with {display_name}', user["sub"])

    return row


@app.get("/api/interviews/{room_id}/access", tags=["Interviews"])
def interview_access(room_id: str, user: dict = Depends(get_current_user)):
    """
    Check karta hai ki user is room mein enter kar sakta hai ya nahi.
    HR (creator) ya candidate (email match) allowed hain.
    """
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

# ============================================================================
# ACTIVITY ROUTES
# ============================================================================

@app.get("/api/activities", tags=["Activities"])
def list_activities(user: dict = Depends(get_current_user)):
    """
    Recent 50 activities.
    HR ko sirf apni, baaki roles ko saari activities dikhti hain.
    """
    conn = get_conn()
    cur = conn.cursor()

    if user["role"] == "hr":
        cur.execute(
            "SELECT * FROM activities WHERE user_id=%s ORDER BY created_at DESC LIMIT 50",
            (user["sub"],)
        )
    else:
        cur.execute("SELECT * FROM activities ORDER BY created_at DESC LIMIT 50")

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/api/health", tags=["System"])
def health():
    """Backend alive check"""
    return {"ok": True}

# ============================================================================
# SOCKET.IO EVENT HANDLERS (WebRTC Signaling)
# ============================================================================

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")


@sio.event
async def join_room(sid, data):
    """
    User interview room mein join karta hai.
    Token verify karta hai, phir room mein add karta hai.
    Dusre participants ko 'peer_joined' event bhejta hai.
    """
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
    print(f"[room {room}] {user_name} joined")


@sio.event
async def leave_room(sid, data):
    """User room chhod raha hai"""
    room = data.get("room")
    if room:
        await sio.leave_room(sid, room)
        await sio.emit("peer_left", {"sid": sid}, room=room)


@sio.event
async def webrtc_offer(sid, data):
    """WebRTC offer relay — HR se candidate ko"""
    await sio.emit("webrtc_offer", data, room=data.get("room"), skip_sid=sid)


@sio.event
async def webrtc_answer(sid, data):
    """WebRTC answer relay — candidate se HR ko"""
    await sio.emit("webrtc_answer", data, room=data.get("room"), skip_sid=sid)


@sio.event
async def webrtc_ice(sid, data):
    """ICE candidate relay — network path dhundhne ke liye"""
    await sio.emit("webrtc_ice", data, room=data.get("room"), skip_sid=sid)


@sio.event
async def chat_message(sid, data):
    """Text chat message relay"""
    await sio.emit("chat_message", data, room=data.get("room"), skip_sid=sid)



@app.on_event("startup")
async def startup():
    """FastAPI startup event — database tables create karta hai agar exist nahi karti"""
    try:
        init_db()
        print("DB initialized successfully")
    except Exception as e:
        print(f"DB init error: {e}")