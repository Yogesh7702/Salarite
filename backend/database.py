# import sqlite3
# import os

# DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salarite.db")


# def get_conn():
#     conn = sqlite3.connect(DB_NAME)
#     conn.row_factory = sqlite3.Row
#     return conn


# def init_db():
#     conn = get_conn()
#     c = conn.cursor()

#     c.executescript("""
#     CREATE TABLE IF NOT EXISTS users (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT NOT NULL,
#         email TEXT UNIQUE NOT NULL,
#         password_hash TEXT NOT NULL,
#         role TEXT NOT NULL CHECK(role IN ('employer','hr','candidate')),
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     );

#     CREATE TABLE IF NOT EXISTS tasks (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         title TEXT NOT NULL,
#         description TEXT,
#         priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
#         status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','in_progress','completed')),
#         employer_id INTEGER NOT NULL,
#         assigned_to INTEGER,
#         started_at TIMESTAMP,
#         completed_at TIMESTAMP,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         FOREIGN KEY(employer_id) REFERENCES users(id) ON DELETE CASCADE,
#         FOREIGN KEY(assigned_to) REFERENCES users(id) ON DELETE SET NULL
#     );

#     CREATE TABLE IF NOT EXISTS interviews (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         candidate_name TEXT,
#         candidate_email TEXT NOT NULL,
#         scheduled_at TEXT NOT NULL,
#         mode TEXT NOT NULL CHECK(mode IN ('voice','video','chat')),
#         room_id TEXT UNIQUE NOT NULL,
#         notes TEXT,
#         created_by INTEGER NOT NULL,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
#     );

#     CREATE TABLE IF NOT EXISTS activities (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         type TEXT NOT NULL,
#         message TEXT NOT NULL,
#         user_id INTEGER,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
#     );
#     """)

#     conn.commit()
#     conn.close()







import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('employer','hr','candidate')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','in_progress','completed')),
        employer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
        id SERIAL PRIMARY KEY,
        candidate_name TEXT,
        candidate_email TEXT NOT NULL,
        scheduled_at TEXT NOT NULL,
        mode TEXT NOT NULL CHECK(mode IN ('voice','video','chat')),
        room_id TEXT UNIQUE NOT NULL,
        notes TEXT,
        created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS activities (
        id SERIAL PRIMARY KEY,
        type TEXT NOT NULL,
        message TEXT NOT NULL,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
    print("DB initialized successfully")