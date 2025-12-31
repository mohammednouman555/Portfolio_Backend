from fastapi import FastAPI, Request
from fastapi import Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
# from sendgrid import SendGridAPIClient
# from sendgrid.helpers.mail import Mail
from database import engine, SessionLocal
from models import ContactMessage
from database import Base
from sqlalchemy import text

app = FastAPI()


origins = [
    "https://mohammednouman555.github.io",
    "http://localhost:63342",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
# TO_EMAIL = os.environ.get("TO_EMAIL")
# FROM_EMAIL = os.environ.get("FROM_EMAIL")


ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")


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

    return {
        "status": "success",
        "message": "Your message has been sent and saved successfully"
    }


@app.get("/admin/messages")
def get_all_messages(request: Request, x_api_key: str = Header(None, alias="x-api-key")):
    if request.headers.get("origin") is not None:
        raise HTTPException(status_code=403, detail="forbidden")
    if not x_api_key or x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=404, detail="Not Found")
    db = SessionLocal()
    messages = db.query(ContactMessage).all()
    db.close()

    return [
        {
            "id": msg.id,
            "name": msg.name,
            "email": msg.email,
            "message": msg.message,
            "is_read": msg.is_read,
            "created_at": msg.created_at
        }
        for msg in messages
    ]


@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "Ok",
            "service": "portfolio-backend",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "portfolio-backend",
            "database": "disconnected",
            "error": str(e)
        }


@app.put("/admin/messages/{message_id}/read")
def mark_message_as_read(message_id: int, request: Request, x_api_key: str = Header(None, alias="x-api-key")):
    if request.headers.get("origin") is not None:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not x_api_key or x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=404, detail="Not Found")

    db = SessionLocal()
    message = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()

    if not message:
        db.close()
        raise HTTPException(status_code=404, detail="Message Not Found")

    message.is_read = True
    db.commit()
    db.close()

    return {
        "status": "success",
        "message": "Message marked as read"
    }
