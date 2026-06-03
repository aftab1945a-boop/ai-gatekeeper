import sqlite3
import bcrypt
import jwt
import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from config import settings

# --- MODELS ---
class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenData(BaseModel):
    user_id: int
    email: str

# --- DATABASE INITIALIZATION ---
def init_auth_tables():
    conn = sqlite3.connect(settings.DATABASE_URL)
    c = conn.cursor()
    
    # Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            subscription_status TEXT DEFAULT 'free',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # API Keys Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_hash TEXT UNIQUE NOT NULL,
            key_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            rate_limit INTEGER DEFAULT 1000,
            requests_today INTEGER DEFAULT 0,
            last_reset TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# Call this once to create tables
init_auth_tables()

# --- HELPER FUNCTIONS ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(user_id: int, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

# --- AUTH ACTIONS ---
def signup_user(user_data: UserSignup) -> dict:
    conn = sqlite3.connect(settings.DATABASE_URL)
    c = conn.cursor()
    
    c.execute("SELECT id FROM users WHERE email = ?", (user_data.email,))
    if c.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = hash_password(user_data.password)
    c.execute('INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)', 
              (user_data.email, password_hash, user_data.full_name))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    
    token = create_access_token(user_id, user_data.email)
    return {"access_token": token, "token_type": "bearer", "user_id": user_id}

def login_user(user_data: UserLogin) -> dict:
    conn = sqlite3.connect(settings.DATABASE_URL)
    c = conn.cursor()
    c.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (user_data.email,))
    user = c.fetchone()
    conn.close()
    
    if not user or not verify_password(user_data.password, user[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(user[0], user[1])
    return {"access_token": token, "token_type": "bearer", "user_id": user[0]}

def generate_api_key(user_id: int, key_name: str) -> dict:
    raw_key = f"gk_{secrets.token_urlsafe(32)}"
    key_hash = hash_password(raw_key)
    
    conn = sqlite3.connect(settings.DATABASE_URL)
    c = conn.cursor()
    c.execute('INSERT INTO api_keys (user_id, key_hash, key_name) VALUES (?, ?, ?)', 
              (user_id, key_hash, key_name))
    conn.commit()
    conn.close()
    
    return {"api_key": raw_key, "key_name": key_name, "message": "Save this key! It won't be shown again."}

def validate_api_key(api_key: str) -> dict:
    """Validate API key using bcrypt comparison (not hash comparison)"""
    conn = sqlite3.connect(settings.DATABASE_URL)
    c = conn.cursor()
    c.execute('''
        SELECT ak.id, ak.user_id, ak.is_active, ak.key_hash, u.email 
        FROM api_keys ak JOIN users u ON ak.user_id = u.id 
        WHERE ak.is_active = 1
    ''')
    all_keys = c.fetchall()
    conn.close()
    
    # Iterate through all keys and check each one with bcrypt
    for key_id, user_id, is_active, key_hash, email in all_keys:
        if verify_password(api_key, key_hash):
            return {"valid": True, "key_id": key_id, "user_id": user_id, "email": email}
    
    return {"valid": False, "error": "Invalid or inactive API key"}