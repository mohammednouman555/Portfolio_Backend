from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlite3

app = FastAPI()

origins = [
    "https://mohammednouman555.github.io",
    "https://mohammednouman555.github.io/Portfolio",
    "https://mohammednouman555.github.io/Portfolio/"
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

#--------DATABASE SETUP--------
def init_db():
    conn = sqlite3.connect("messages.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            message TEXT
        )
        """
    )
    conn.commit
    conn.close()

# ------API

@app.get("/")
def root():
    return {"message": "Backend is running successfully"}


@app.post("/contact")
async def contact(request: Request):
    data = await request.json()
    print("Message Received", data)
    return {"status": "success", "message": "Message received"}
