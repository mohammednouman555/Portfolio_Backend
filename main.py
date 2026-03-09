from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from datetime import datetime, timedelta
import os
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Query
from database import engine, SessionLocal
from models import ContactMessage, AdminActivity
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import BackgroundTasks
from sqlalchemy import inspect


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

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ================== PASSWORD HASHING ==================

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ================== AUTH ==================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")


def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str = Depends(oauth2_scheme)):

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401)

        return username

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


def send_email(name, email, message):

    EMAIL_USER = os.environ.get("EMAIL_USER")
    EMAIL_PASS = os.environ.get("EMAIL_PASS")

    if not EMAIL_USER or not EMAIL_PASS:
        return

    try:
        subject = "New Portfolio Contact Message"

        body = f"""
New message received:

Name: {name}
Email: {email}

Message:
{message}
"""

        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()

    except Exception as e:
        print("Email error:", e)


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

    # run email in background
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

    # LOG LOGIN
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
    read = db.query(ContactMessage).filter(ContactMessage.is_read == True).count()
    unread = db.query(ContactMessage).filter(ContactMessage.is_read == False).count()

    last = db.query(ContactMessage) \
        .order_by(ContactMessage.created_at.desc()) \
        .first()

    db.close()

    return {
        "total_messages": total,
        "read_messages": read,
        "unread_messages": unread,
        "last_message_time": last.created_at if last else None
    }


# ================== TOGGLE READ ==================

@app.put("/admin/messages/{message_id}/toggle-read")
def toggle_read(message_id: int, user: str = Depends(verify_token)):

    db = SessionLocal()

    message = db.query(ContactMessage) \
        .filter(ContactMessage.id == message_id) \
        .first()

    if not message:
        db.close()
        raise HTTPException(status_code=404, detail="Message not found")

    message.is_read = not message.is_read

    db.commit()
    db.refresh(message)
    db.close()

    # LOG ACTION
    log_admin_action(user, f"Toggled read for message {message_id}")

    return {
        "status": "success",
        "id": message.id,
        "is_read": message.is_read
    }


# ================== DELETE MESSAGE ==================

@app.delete("/admin/messages/{message_id}")
def delete_message(message_id: int, user: str = Depends(verify_token)):

    db = SessionLocal()

    msg = db.query(ContactMessage) \
        .filter(ContactMessage.id == message_id) \
        .first()

    if not msg:
        db.close()
        raise HTTPException(status_code=404, detail="Message not found")

    db.delete(msg)
    db.commit()
    db.close()

    # LOG ACTION
    log_admin_action(user, f"Deleted message {message_id}")

    return {
        "status": "success",
        "message": "Message deleted"
    }


# ================== GET ACTIVITY ==================

@app.get("/admin/activity")
def get_activity(user: str = Depends(verify_token)):

    db = SessionLocal()

    logs = db.query(AdminActivity) \
        .order_by(AdminActivity.created_at.desc()) \
        .limit(20) \
        .all()

    db.close()

    return [
        {
            "id": log.id,
            "username": log.username,
            "action": log.action,
            "created_at": log.created_at
        }
        for log in logs
    ]


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


@app.get("/debug/schema")
def debug_schema():
    inspector = inspect(engine)
    columns = inspector.get_columns("contact_messages")

    result = []
    for col in columns:
        result.append({
            "name": col["name"],
            "type": str(col["type"]),
            "default": str(col.get("default")),
            "nullable": col.get("nullable")
        })

    return result
