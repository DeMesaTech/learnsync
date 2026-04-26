from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# CORS Configuration
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoint
class ItemData(BaseModel):
    data: str

@app.post("/api/process")
async def process_item(item: ItemData):
    if not item.data:
        raise HTTPException(status_code=400, detail="No data provided")
    processed_message = f"Backend received: {item.data}"
    return {"message": processed_message}

# Serve static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")