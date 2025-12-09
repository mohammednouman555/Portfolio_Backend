from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
def root():
    return {"message": "Backend is running successfully"}


@app.post("/contact")
async def contact(request: Request):
    data = await request.json()
    print("Message Received", data)
    return {"status": "success", "message": "Message received"}
