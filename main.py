from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
import os
import smtplib
from email.mime.text import MIMEText
from fastapi.responses import StreamingResponse
import io, csv

from database import engine, SessionLocal
from models import Base, ContactMessage

# ================= APP =================
app = FastAPI()
Base.metadata.create_all(bind=engine)

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= AUTH =================
ADMIN_USER = os.environ.get("ADMIN_USER")
ADMIN_PASS_HASH = os.environ.get("ADMIN_PASS_HASH")
SECRET_KEY = os.environ.get("SECRET_KEY", "secret")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")

def create_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        raise HTTPException(status_code=401)

# ================= EMAIL =================
def send_email(name, email, message):
    EMAIL_USER = os.environ.get("EMAIL_USER")
    EMAIL_PASS = os.environ.get("EMAIL_PASS")

    try:
        msg = MIMEText(f"{name}\n{email}\n\n{message}")
        msg["Subject"] = "Portfolio Message"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email error:", e)

# ================= CONTACT =================
@app.post("/contact")
async def contact(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()

    db = SessionLocal()
    msg = ContactMessage(
        name=data["name"],
        email=data["email"],
        message=data["message"],
        created_at=datetime.utcnow()
    )
    db.add(msg)
    db.commit()
    db.close()

    background_tasks.add_task(send_email, data["name"], data["email"], data["message"])

    return {"status": "success"}

# ================= LOGIN =================
@app.post("/admin/login")
def login(data: dict):
    if data["username"] != ADMIN_USER:
        raise HTTPException(status_code=401)

    if not pwd_context.verify(data["password"], ADMIN_PASS_HASH):
        raise HTTPException(status_code=401)

    return {"access_token": create_token({"sub": data["username"]})}

# ================= GET MESSAGES =================
@app.get("/admin/messages")
def get_messages(user: dict = Depends(verify_token)):
    db = SessionLocal()

    msgs = db.query(ContactMessage)\
        .order_by(ContactMessage.created_at.desc())\
        .all()

    db.close()

    return {
        "messages": [
            {
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "message": m.message,
                "is_read": m.is_read,
                "created_at": m.created_at
            }
            for m in msgs
        ]
    }

# ================= DELETE =================
@app.delete("/admin/messages/{id}")
def delete_msg(id: int, user: dict = Depends(verify_token)):
    db = SessionLocal()
    msg = db.query(ContactMessage).filter(ContactMessage.id == id).first()

    if msg:
        db.delete(msg)
        db.commit()

    db.close()
    return {"status": "deleted"}

# ================= TOGGLE =================
@app.put("/admin/messages/{id}/toggle-read")
def toggle(id: int, user: dict = Depends(verify_token)):
    db = SessionLocal()
    msg = db.query(ContactMessage).filter(ContactMessage.id == id).first()

    if msg:
        msg.is_read = not msg.is_read
        db.commit()

    db.close()
    return {"status": "updated"}

# ================= STATS =================
@app.get("/admin/stats")
def stats(user: dict = Depends(verify_token)):
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

# ================= EXPORT =================
@app.get("/admin/export")
def export(user: dict = Depends(verify_token)):
    db = SessionLocal()
    msgs = db.query(ContactMessage).all()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name","Email","Message","Date"])

    for m in msgs:
        writer.writerow([m.name, m.email, m.message, m.created_at])

    output.seek(0)

    return StreamingResponse(output, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=messages.csv"})