from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from datetime import datetime, timedelta
import os
from jose import JWTError, jwt
from passlib.context import CryptContext

from database import engine, SessionLocal
from models import ContactMessage


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
ACCESS_TOKEN_EXPIRE_MINUTES = 1


# ================== PASSWORD HASHING ==================

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


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

    return {
        "status": "success",
        "message": "Your message has been sent"
    }


# ================== ADMIN LOGIN ==================

@app.post("/admin/login")
def admin_login(data: dict):

    username = data.get("username")
    password = data.get("password")

    # Check username
    if username != ADMIN_USER:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    # Check password using hash
    if not pwd_context.verify(password, ADMIN_PASS_HASH):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    # Create JWT token
    token = create_token({"sub": username})

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# ================== GET MESSAGES ==================

@app.get("/admin/messages")
def get_messages(user: str = Depends(verify_token)):

    db = SessionLocal()

    messages = db.query(ContactMessage)\
        .order_by(ContactMessage.created_at.desc())\
        .all()

    db.close()

    return [
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


# ================== TOGGLE READ ==================

@app.put("/admin/messages/{message_id}/toggle-read")
def toggle_read(
    message_id: int,
    user: str = Depends(verify_token)
):

    db = SessionLocal()

    message = db.query(ContactMessage)\
        .filter(ContactMessage.id == message_id)\
        .first()

    if not message:
        db.close()
        raise HTTPException(
            status_code=404,
            detail="Message not found"
        )

    message.is_read = not message.is_read

    db.commit()
    db.refresh(message)
    db.close()

    return {
        "status": "success",
        "id": message.id,
        "is_read": message.is_read
    }


# ================== DELETE MESSAGE ==================

@app.delete("/admin/messages/{message_id}")
def delete_message(
    message_id: int,
    user: str = Depends(verify_token)
):

    db = SessionLocal()

    msg = db.query(ContactMessage)\
        .filter(ContactMessage.id == message_id)\
        .first()

    if not msg:
        db.close()
        raise HTTPException(
            status_code=404,
            detail="Message not found"
        )

    db.delete(msg)
    db.commit()
    db.close()

    return {
        "status": "success",
        "message": "Message deleted"
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