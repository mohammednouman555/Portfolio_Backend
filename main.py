from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Query
import os
import smtplib
from email.mime.text import MIMEText
from fastapi.responses import StreamingResponse
import io
import csv

from database import engine, SessionLocal
from models import Base, ContactMessage, AdminActivity

# ================== APP ==================
app = FastAPI()

# ================== DB INIT ==================
Base.metadata.create_all(bind=engine)

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

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")

# ================== TOKEN ==================
def create_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=30)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except:
        raise HTTPException(status_code=401)

# ================== EMAIL ==================
def send_email(name, email, message):
    EMAIL_USER = os.environ.get("EMAIL_USER")
    EMAIL_PASS = os.environ.get("EMAIL_PASS")

    try:
        msg = MIMEText(f"{name}\n{email}\n\n{message}")
        msg["Subject"] = "New Portfolio Message"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email error:", e)

# ================== CONTACT ==================
@app.post("/contact")
async def contact(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    db = SessionLocal()

    msg = ContactMessage(
        name=data["name"],
        email=data["email"],
        message=data["message"]
    )

    db.add(msg)
    db.commit()
    db.close()

    background_tasks.add_task(send_email, data["name"], data["email"], data["message"])

    return {"status": "success"}

# ================== LOGIN ==================
@app.post("/admin/login")
def login(data: dict):
    if data["username"] != ADMIN_USER:
        raise HTTPException(status_code=401)

    if not pwd_context.verify(data["password"], ADMIN_PASS_HASH):
        raise HTTPException(status_code=401)

    return {"access_token": create_token({"sub": data["username"]})}

# ================== GET MESSAGES ==================
@app.get("/admin/messages")
def get_messages(
    user: str = Depends(verify_token),
    page: int = 1,
    limit: int = 5,
    search: str = ""
):
    db = SessionLocal()

    query = db.query(ContactMessage)

    if search:
        query = query.filter(
            ContactMessage.name.ilike(f"%{search}%")
        )

    total = query.count()

    messages = query.order_by(ContactMessage.created_at.desc())\
        .offset((page-1)*limit)\
        .limit(limit)\
        .all()

    db.close()

    return {
        "total": total,
        "messages": messages
    }

# ================== DELETE ==================
@app.delete("/admin/messages/{id}")
def delete_msg(id: int, user: str = Depends(verify_token)):
    db = SessionLocal()

    msg = db.query(ContactMessage).filter(ContactMessage.id == id).first()
    db.delete(msg)
    db.commit()
    db.close()

    return {"status": "deleted"}

# ================== TOGGLE ==================
@app.put("/admin/messages/{id}/toggle-read")
def toggle(id: int, user: str = Depends(verify_token)):
    db = SessionLocal()
    msg = db.query(ContactMessage).get(id)
    msg.is_read = not msg.is_read
    db.commit()
    db.close()
    return {"status": "updated"}

# ================== STATS ==================
@app.get("/admin/stats")
def stats(user: str = Depends(verify_token)):
    db = SessionLocal()

    total = db.query(ContactMessage).count()
    read = db.query(ContactMessage).filter_by(is_read=True).count()
    unread = db.query(ContactMessage).filter_by(is_read=False).count()
    last = db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).first()

    db.close()

    return {
        "total_messages": total,
        "read_messages": read,
        "unread_messages": unread,
        "last_message_time": last.created_at if last else None
    }

# ================== ACTIVITY ==================
@app.get("/admin/activity")
def activity(user: str = Depends(verify_token)):
    db = SessionLocal()

    logs = db.query(AdminActivity)\
        .order_by(AdminActivity.created_at.desc())\
        .limit(10).all()

    db.close()
    return logs

# ================== EXPORT CSV ==================
@app.get("/admin/export")
def export(user: str = Depends(verify_token)):
    db = SessionLocal()
    messages = db.query(ContactMessage).all()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Name","Email","Message","Date"])

    for m in messages:
        writer.writerow([m.name, m.email, m.message, m.created_at])

    output.seek(0)

    return StreamingResponse(output, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=messages.csv"})