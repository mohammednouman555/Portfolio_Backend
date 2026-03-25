from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Query
import os
import requests
from database import engine, SessionLocal
from models import Base, ContactMessage, AdminActivity


# ================== APP ==================

app = FastAPI()


# ================== CORS ==================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mohammednouman555.github.io",
        "http://localhost:63342"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================== ENV ==================

ADMIN_USER = os.environ.get("ADMIN_USER")
ADMIN_PASS_HASH = os.environ.get("ADMIN_PASS_HASH")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ================== PASSWORD HASHING ==================

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ================== AUTH ==================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")


def create_token(data: dict):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def verify_token(token: str = Depends(oauth2_scheme)):

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401)

        return username

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


# ================== SEND EMAIL ==================

import requests
import os

def send_email(name: str, email: str, message: str):

    API_KEY = os.environ.get("RESEND_API_KEY")

    if not API_KEY:
        print("❌ Resend API key missing")
        return

    url = "https://api.resend.com/emails"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # ================== EMAIL TO YOU ==================

    admin_html = f"""
    <h2>📩 New Portfolio Message</h2>
    <p><strong>Name:</strong> {name}</p>
    <p><strong>Email:</strong> {email}</p>
    <p><strong>Message:</strong></p>
    <div style="background:#f4f4f4;padding:10px;border-radius:5px;">
        {message}
    </div>
    """

    admin_data = {
        "from": "Portfolio <onboarding@resend.dev>",
        "to": ["mohammednouman555@gmail.com"],
        "subject": "New Portfolio Message",
        "html": admin_html
    }

    # ================== AUTO REPLY TO USER ==================

    user_html = f"""
    <h2>Thank you, {name}!</h2>
    <p>Your message has been received successfully.</p>

    <p>I will get back to you soon.</p>

    <hr>

    <p><strong>Your Message:</strong></p>
    <div style="background:#f9f9f9;padding:10px;border-radius:5px;">
        {message}
    </div>

    <br>
    <p>— Mohammed Nouman</p>
    """

    user_data = {
        "from": "Mohammed Nouman <onboarding@resend.dev>",
        "to": [email],
        "subject": "We received your message",
        "html": user_html
    }

    try:
        # Send to admin
        res1 = requests.post(url, headers=headers, json=admin_data)
        print("📨 Admin mail:", res1.status_code)

        # Send auto-reply
        res2 = requests.post(url, headers=headers, json=user_data)
        print("📨 User mail:", res2.status_code)

    except Exception as e:
        print("❌ Email error:", e)

# ================== ACTIVITY LOGGER ==================

def log_admin_action(username: str, action: str):

    db = SessionLocal()

    log = AdminActivity(
        username=username,
        action=action
    )

    db.add(log)
    db.commit()
    db.close()


# ================== ROUTES ==================

@app.get("/")
def root():
    return {"message": "Backend is running successfully"}


# ================== CONTACT ==================

@app.post("/contact")
async def contact(request: Request):

    data = await request.json()

    db = SessionLocal()

    new_message = ContactMessage(
        name=data.get("name"),
        email=data.get("email"),
        message=data.get("message")
    )

    db.add(new_message)
    db.commit()
    db.close()

    # 🚀 CALL EMAIL DIRECTLY (IMPORTANT FIX)
    send_email(
        data.get("name"),
        data.get("email"),
        data.get("message")
    )

    return {
        "status": "success",
        "message": "Your message has been sent"
    }

# ================== ADMIN LOGIN ==================

@app.post("/admin/login")
def admin_login(data: dict):

    username = data.get("username")
    password = data.get("password")

    if username != ADMIN_USER:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not pwd_context.verify(password, ADMIN_PASS_HASH):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"sub": username})

    log_admin_action(username, "Admin logged in")

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# ================== GET MESSAGES ==================

@app.get("/admin/messages")
def get_messages(
    user: str = Depends(verify_token),
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1, le=50),
    search: str = Query(None)
):

    db = SessionLocal()

    query = db.query(ContactMessage)

    if search:
        query = query.filter(
            (ContactMessage.name.ilike(f"%{search}%")) |
            (ContactMessage.email.ilike(f"%{search}%"))
        )

    total = query.count()

    messages = query \
        .order_by(ContactMessage.created_at.desc()) \
        .offset((page - 1) * limit) \
        .limit(limit) \
        .all()

    db.close()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "messages": [
            {
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "message": m.message,
                "is_read": m.is_read,
                "created_at": m.created_at
            }
            for m in messages
        ]
    }


# ================== ADMIN STATS ==================

@app.get("/admin/stats")
def admin_stats(user: str = Depends(verify_token)):

    db = SessionLocal()

    total = db.query(ContactMessage).count()

    read = db.query(ContactMessage)\
        .filter(ContactMessage.is_read == True)\
        .count()

    unread = db.query(ContactMessage)\
        .filter(ContactMessage.is_read == False)\
        .count()

    last = db.query(ContactMessage)\
        .order_by(ContactMessage.created_at.desc())\
        .first()

    db.close()

    return {
        "total_messages": total,
        "read_messages": read,
        "unread_messages": unread,
        "last_message_time": last.created_at if last else None
    }


# ================== HEALTH ==================

@app.get("/health")
def health():

    try:

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        return {
            "status": "Ok",
            "database": "connected"
        }

    except Exception as e:

        return {
            "status": "degraded",
            "database": "disconnected",
            "error": str(e)
        }