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
from models import ContactMessage, AdminActivity


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

def send_email(name: str, email: str, message: str):

    if not SENDGRID_API_KEY:
        print("SendGrid API key missing")
        return

    url = "https://api.sendgrid.com/v3/mail/send"

    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "personalizations": [
            {
                "to": [{"email": "mohammednouman555@gmail.com"}],
                "subject": "New Portfolio Contact Message"
            }
        ],
        "from": {
            "email": "mohammednouman555@gmail.com",
            "name": "Portfolio Contact"
        },
        "reply_to": {
            "email": email
        },
        "content": [
            {
                "type": "text/plain",
                "value": f"""
New message received from portfolio:

Name: {name}
Email: {email}

Message:
{message}
"""
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data)

        print("SendGrid Status:", response.status_code)
        print("SendGrid Response:", response.text)

    except Exception as e:
        print("Email sending failed:", e)

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
async def contact(
    request: Request,
    background_tasks: BackgroundTasks
):

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

    # send email in background
    background_tasks.add_task(
        send_email,
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