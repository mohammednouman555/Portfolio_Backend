from fastapi import FastAPI, Request, HTTPException, Depends
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
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ================== PASSWORD HASHING ==================
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ================== AUTH ==================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")


def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
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
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ================== EMAIL ==================
def send_email(name: str, email: str, message: str):

    if not RESEND_API_KEY:
        print("❌ Resend API key missing")
        return

    url = "https://api.resend.com/emails"

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    # Admin Email
    admin_html = f"""
    <h2>📩 New Portfolio Message</h2>
    <p><b>Name:</b> {name}</p>
    <p><b>Email:</b> {email}</p>
    <p><b>Message:</b></p>
    <div style="background:#f4f4f4;padding:10px;border-radius:5px;">
        {message}
    </div>
    """

    # User Auto Reply
    user_html = f"""
    <h2>Thank you, {name}!</h2>
    <p>Your message has been received.</p>
    <p>I will contact you soon.</p>

    <hr>

    <p><b>Your Message:</b></p>
    <div style="background:#f9f9f9;padding:10px;border-radius:5px;">
        {message}
    </div>

    <br>
    <p>— Mohammed Nouman</p>
    """

    try:
        # send to admin
        requests.post(url, headers=headers, json={
            "from": "Portfolio <onboarding@resend.dev>",
            "to": ["mohammednouman555@gmail.com"],
            "subject": "New Portfolio Message",
            "html": admin_html
        })

        # auto reply
        requests.post(url, headers=headers, json={
            "from": "Nouman <onboarding@resend.dev>",
            "to": [email],
            "subject": "We received your message",
            "html": user_html
        })

        print("✅ Emails sent")

    except Exception as e:
        print("❌ Email error:", e)


# ================== ROUTES ==================

@app.get("/")
def root():
    return {"message": "Backend is running successfully"}


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

    # Direct call (important)
    send_email(
        data.get("name"),
        data.get("email"),
        data.get("message")
    )

    return {"status": "success"}


@app.post("/admin/login")
def admin_login(data: dict):

    if data.get("username") != ADMIN_USER:
        raise HTTPException(status_code=401)

    if not pwd_context.verify(data.get("password"), ADMIN_PASS_HASH):
        raise HTTPException(status_code=401)

    token = create_token({"sub": data.get("username")})

    return {"access_token": token}


@app.get("/admin/messages")
def get_messages(
    user: str = Depends(verify_token),
    page: int = 1,
    limit: int = 5,
    search: str = None
):

    db = SessionLocal()

    query = db.query(ContactMessage)

    if search:
        query = query.filter(
            (ContactMessage.name.ilike(f"%{search}%")) |
            (ContactMessage.email.ilike(f"%{search}%"))
        )

    total = query.count()

    messages = query.order_by(ContactMessage.created_at.desc()) \
        .offset((page - 1) * limit) \
        .limit(limit).all()

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
            } for m in messages
        ]
    }


@app.get("/admin/stats")
def stats(user: str = Depends(verify_token)):

    db = SessionLocal()

    total = db.query(ContactMessage).count()
    read = db.query(ContactMessage).filter(ContactMessage.is_read == True).count()
    unread = db.query(ContactMessage).filter(ContactMessage.is_read == False).count()

    last = db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).first()

    db.close()

    return {
        "total_messages": total,
        "read_messages": read,
        "unread_messages": unread,
        "last_message_time": last.created_at if last else None
    }