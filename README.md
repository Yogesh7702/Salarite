# Salarite

This is a full-stack hiring workflow app built with Flask and React. It supports role-based login, task management between Employer and HR users, interview scheduling, and a real-time call room. [web:584][web:587]

## Tech Stack

- Frontend: React, Vite, React Router, Axios
- Backend: Flask, Flask-SocketIO, SQLite, JWT
- Realtime: Socket.IO, WebRTC [web:593]

## Run Locally

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Runs on `http://localhost:5001`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`. [web:584][web:593]

## Environment

### backend/.env.example
```env
SECRET_KEY=your-super-secret-key-here-minimum-32-chars
FRONTEND_URL=http://localhost:5173
PORT=5001
```

### frontend/.env.example
```env
VITE_API_URL=http://localhost:5001
VITE_SOCKET_URL=http://localhost:5001
``` [web:587]

## Features

- Role-based authentication
- Employer and HR dashboards
- Task assignment and status updates
- Interview scheduling
- Real-time call room [web:593]

## Author

Built by Yogesh.
```

Ab isko `README.md` me paste kar de, phir:
```bash
git add README.md
git status
```