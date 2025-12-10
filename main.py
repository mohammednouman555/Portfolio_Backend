from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

load_dotenv()

app = FastAPI()

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

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
TO_EMAIL = "mohammednouman555@gmail.com"
FROM_EMAIL = "mohammednouman555@gmail.com"  # Sender identity


@app.get("/")
def root():
    return {"message": "Backend is running successfully"}


@app.post("/contact")
async def contact(request: Request):
    data = await request.json()

    user_name = data.get("name")
    user_email = data.get("email")
    user_message = data.get("message")

    email_subject = f"New Portfolio Message from {user_name}"
    email_content = f"""
    Name: {user_name}
    Email: {user_email}
    Message:
    {user_message}
    """

    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=TO_EMAIL,
        subject=email_subject,
        plain_text_content=email_content
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        return {"status": "success", "message": "Your message has been sent successfully!"}
    except Exception as e:
        print("Email Error:", e)
        return {"status": "error", "message": "Failed to send message"}
