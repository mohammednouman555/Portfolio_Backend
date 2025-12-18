from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
# from sendgrid import SendGridAPIClient
# from sendgrid.helpers.mail import Mail
from database import engine, SessionLocal
from models import ContactMessage
from database import Base

app = FastAPI()

Base.metadata.create_all(bind=engine)

origins = [
    "https://mohammednouman555.github.io",
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
def get_all_messages():
    db = SessionLocal()
    messages = db.query(ContactMessage).all()
    db.close()

    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "name": msg.user_name,
            "email": msg.user_email,
            "message": msg.user_message
        })
    return result


#     email_subject = f"New Portfolio Message from {user_name}"
#     email_content = f"""
# Name: {user_name}
# Email: {user_email}
# Message:
# {user_message}
# """
#
#     message = Mail(
#         from_email=FROM_EMAIL,
#         to_emails=TO_EMAIL,
#         subject=email_subject,
#         plain_text_content=email_content
#     )
#
#     try:
#         sg = SendGridAPIClient(SENDGRID_API_KEY)
#         sg.send(message)
#         return {"status": "success", "message": "Your message has been sent successfully!"}
#     except Exception as e:
#         print("Email Error:", e)
#         return {"status": "error", "message": "Failed to send message"}
