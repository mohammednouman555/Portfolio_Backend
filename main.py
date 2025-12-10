from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

EMAIL_ADDRESS = "mohdnouman555@gmail.com"  # Your Gmail
EMAIL_PASSWORD = "slap tath cods yhrq"  # Replace with App Password

@app.get("/")
def root():
    return {"message": "Backend is running successfully"}

@app.post("/contact")
async def contact(request: Request):
    data = await request.json()

    user_name = data.get("name")
    user_email = data.get("email")
    user_message = data.get("message")

    # Email content
    subject = f"Portfolio Contact from {user_name}"
    body = f"Name: {user_name}\nEmail: {user_email}\nMessage:\n{user_message}"

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        return {"status": "success", "message": "Your message has been sent successfully!"}
    except Exception as e:
        print("Email Error:", e)
        return {"status": "error", "message": "Failed to send message"}
