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
import csv
import io

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.responses import StreamingResponse

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

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ================== PASSWORD ==================

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
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ================== EMAIL (PREMIUM HTML) ==================

def send_email(name, email, message):

    EMAIL_USER = os.environ.get("EMAIL_USER")
    EMAIL_PASS = os.environ.get("EMAIL_PASS")

    if not EMAIL_USER or not EMAIL_PASS:
        print("Email config missing")
        return

    try:

        html = f"""
        <html>
        <body style="font-family:Arial; background:#f4f6f9; padding:20px;">
            <div style="max-width:600px; margin:auto; background:white; padding:20px; border-radius:10px;">
                <h2 style="color:#0077b6;">📩 New Portfolio Message</h2>

                <p><b>Name:</b> {name}</p>
                <p><b>Email:</b> {email}</p>

                <div style="margin-top:15px; padding:15px; background:#f1f1f1; border-radius:8px;">
                    {message}
                </div>

                <p style="margin-top:20px; font-size:12px; color:gray;">
                    Sent from your portfolio website
                </p>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "New Portfolio Message"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER

        msg.attach(MIMEText(html, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()

        print("Email sent successfully")

    except Exception as e:
        print("Email error:", e)


# ================== ACTIVITY LOG ==================

def log_admin_action(username: str, action: str):
    db = SessionLocal()

    log = AdminActivity(
        username=username,
        action=action
    )

    db.add(log)
    db.commit()
    db.close()


# ================== ROOT ==================

@app.get("/")
def root():
    return {"message": "Backend is running successfully"}


# ================== CONTACT ==================

@app.post("/contact")
async def contact(request: Request, background_tasks: BackgroundTasks):

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

    # send email
    background_tasks.add_task(
        send_email,
        data.get("name"),
        data.get("email"),
        data.get("message")
    )

    return {"status": "success", "message": "Message sent"}


# ================== LOGIN ==================

@app.post("/admin/login")
def admin_login(data: dict):

    username = data.get("username")
    password = data.get("password")

    if username != ADMIN_USER:
        raise HTTPException(status_code=401)

    if not pwd_context.verify(password, ADMIN_PASS_HASH):
        raise HTTPException(status_code=401)

    token = create_token({"sub": username})

    log_admin_action(username, "Admin logged in")

    return {"access_token": token, "token_type": "bearer"}


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

    messages = query.order_by(ContactMessage.created_at.desc()) \
        .offset((page - 1) * limit) \
        .limit(limit) \
        .all()

    db.close()

    return {
        "total": total,
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


# ================== STATS ==================

@app.get("/admin/stats")
def admin_stats(user: str = Depends(verify_token)):

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


# ================== TOGGLE ==================

@app.put("/admin/messages/{message_id}/toggle-read")
def toggle_read(message_id: int, user: str = Depends(verify_token)):

    db = SessionLocal()

    message = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()

    if not message:
        db.close()
        raise HTTPException(status_code=404)

    message.is_read = not message.is_read

    db.commit()
    db.refresh(message)
    db.close()

    log_admin_action(user, f"Toggled message {message_id}")

    return {"status": "success"}


# ================== DELETE ==================

@app.delete("/admin/messages/{message_id}")
def delete_message(message_id: int, user: str = Depends(verify_token)):

    db = SessionLocal()

    msg = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()

    if not msg:
        db.close()
        raise HTTPException(status_code=404)

    db.delete(msg)
    db.commit()
    db.close()

    log_admin_action(user, f"Deleted message {message_id}")

    return {"status": "deleted"}


# ================== EXPORT CSV ==================

@app.get("/admin/export")
def export_messages(user: str = Depends(verify_token)):

    db = SessionLocal()
    messages = db.query(ContactMessage).all()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Name", "Email", "Message", "Date"])

    for m in messages:
        writer.writerow([m.name, m.email, m.message, m.created_at])

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=messages.csv"}
    )


# ================== HEALTH ==================

@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        return {"status": "OK"}

    except Exception as e:
        return {"status": "error", "detail": str(e)}