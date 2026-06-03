import time
import sqlite3
import httpx
import jwt
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List

# Humari banayi hui files ko import karna
from config import settings
from logger_config import logger
from auth_system import (
    UserSignup, UserLogin, signup_user, login_user, 
    generate_api_key, validate_api_key
)
from smart_router import analyze_intent

# --- APP SETUP ---
app = FastAPI(
    title="AI Gatekeeper Proxy",
    description="Smart AI Routing & Cost Optimization",
    version="1.0.0"
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STATIC FILES SETUP ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

# --- MODELS ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class ChatResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[dict]
    usage: dict
    routing_info: dict

class APIKeyRequest(BaseModel):
    key_name: str

# --- DATABASE LOGGING FUNCTION (NEW!) ---
def log_request_to_db(user_id: int, source: str, model: str, cost: float, latency: float):
    """Request ko database mein save karta hai"""
    try:
        conn = sqlite3.connect(settings.DATABASE_URL)
        c = conn.cursor()
        
        # Usage logs table create karein agar nahi hai
        c.execute('''
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp TEXT,
                source TEXT,
                model_used TEXT,
                cost_usd REAL,
                latency_seconds REAL
            )
        ''')
        
        # Data insert karein
        c.execute('''
            INSERT INTO usage_logs (user_id, timestamp, source, model_used, cost_usd, latency_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, time.strftime('%Y-%m-%d %H:%M:%S'), source, model, cost, latency))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Request logged to database")
    except Exception as e:
        logger.error(f"DB Logging Error: {str(e)}")

# --- HELPER FUNCTIONS (AI Calls) ---
async def call_ollama(messages: List[Message]) -> dict:
    """Local Ollama Model ko call karein"""
    payload = {
        "model": "llama3.2:1b",  # Chota model use kar rahe hain
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": False
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post("http://localhost:11434/api/chat", json=payload, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            return {
                "source": "LOCAL",
                "content": data['message']['content'],
                "model": "llama3.2:1b",
                "prompt_tokens": 0,
                "completion_tokens": 0
            }
        except Exception as e:
            logger.error(f"Ollama Error: {str(e)}")
            raise HTTPException(status_code=500, detail="Local model failed. Is Ollama running?")

async def call_openai(messages: List[Message]) -> dict:
    """Cloud OpenAI Model ko call karein"""
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": False
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            return {
                "source": "CLOUD",
                "content": data['choices'][0]['message']['content'],
                "model": "gpt-4o-mini",
                "prompt_tokens": data['usage']['prompt_tokens'],
                "completion_tokens": data['usage']['completion_tokens']
            }
        except Exception as e:
            logger.error(f"OpenAI Error: {str(e)}")
            raise HTTPException(status_code=500, detail="Cloud model failed.")

# --- API ENDPOINTS ---

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/auth/signup")
def signup(user_data: UserSignup):
    return signup_user(user_data)

@app.post("/auth/login")
def login(user_data: UserLogin):
    return login_user(user_data)

# --- DASHBOARD STATS ENDPOINT (NEW!) ---
@app.get("/dashboard/stats")
def get_dashboard_stats(authorization: str = Header(None)):
    """User ke dashboard ke liye real stats fetch karta hai"""
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = payload["user_id"]
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    conn = sqlite3.connect(settings.DATABASE_URL)
    c = conn.cursor()
    
    # Total Requests
    c.execute("SELECT COUNT(*) FROM usage_logs WHERE user_id = ?", (user_id,))
    total_requests = c.fetchone()[0] or 0
    
    # Total Cost
    c.execute("SELECT SUM(cost_usd) FROM usage_logs WHERE user_id = ? AND source = 'CLOUD'", (user_id,))
    total_cost = c.fetchone()[0] or 0.0
    
    # Local vs Cloud Count
    c.execute("SELECT source, COUNT(*) FROM usage_logs WHERE user_id = ? GROUP BY source", (user_id,))
    routing_data = dict(c.fetchall())
    
    conn.close()
    
    return {
        "total_requests": total_requests,
        "total_cost_saved": round(total_cost, 4),
        "local_requests": routing_data.get('LOCAL', 0),
        "cloud_requests": routing_data.get('CLOUD', 0)
    }

# --- API KEY GENERATION ---
@app.post("/api-keys/generate")
def create_api_key(
    request: APIKeyRequest,
    authorization: str = Header(None, description="Bearer token")
):
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    return generate_api_key(user_id, request.key_name)

# --- THE CORE PROXY ROUTE ---
@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    x_api_key: str = Header(None, description="Your API Key"),
    authorization: str = Header(None, description="Bearer token")
):
    start_time = time.time()
    
    # 1. Validate API Key or JWT Token
    user_id = None
    if x_api_key:
        auth_result = validate_api_key(x_api_key)
        if auth_result.get("valid"):
            user_id = auth_result["user_id"]
        else:
            raise HTTPException(status_code=401, detail=auth_result["error"])
    elif authorization:
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid authorization header")
    else:
        raise HTTPException(status_code=401, detail="Missing API key or Authorization header")
    
    # 2. Prompt Analyze karein (Smart Routing)
    last_message = request.messages[-1].content if request.messages else ""
    analysis = analyze_intent(last_message)
    
    logger.info(f"Routing Decision: {analysis['decision']} | Reasons: {analysis['reasons']}")
    
    # 3. Model Call karein
    try:
        if analysis['decision'] == "LOCAL":
            result = await call_ollama(request.messages)
        else:
            result = await call_openai(request.messages)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    end_time = time.time()
    latency = round(end_time - start_time, 2)
    
    # 4. Cost Calculate karein
    cost_estimate = 0.0
    if result['source'] == 'CLOUD':
        cost_estimate = (result['prompt_tokens'] * 0.00000015) + (result['completion_tokens'] * 0.00000060)
    
    logger.info(f"Request Completed | Source: {result['source']} | Latency: {latency}s | Cost: ${cost_estimate:.6f}")
    
    # 5. LOG TO DATABASE (NEW!)
    log_request_to_db(user_id, result['source'], result['model'], cost_estimate, latency)
    
    # 6. Response Return karein
    return ChatResponse(
        id=f"gk-{int(time.time())}",
        object="chat.completion",
        created=int(time.time()),
        model=result['model'],
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": result['content']},
            "finish_reason": "stop"
        }],
        usage={
            "prompt_tokens": result['prompt_tokens'],
            "completion_tokens": result['completion_tokens'],
            "total_tokens": result['prompt_tokens'] + result['completion_tokens']
        },
        routing_info={
            "decision": analysis['decision'],
            "confidence": analysis['confidence'],
            "reasons": analysis['reasons']
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)