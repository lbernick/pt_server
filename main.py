from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="PT Server", version="1.0.0")


@app.get("/")
async def root():
    return {"message": "Welcome to PT Server"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
