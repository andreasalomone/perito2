import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import lifespan
from config import settings
from core.models import ReportLog, DocumentLog

# Import routers
from routes import reports, tasks, auth

app = FastAPI(
    title="RobotPerizia API",
    lifespan=lifespan # Connects the DB on startup
)

# CORS: Allow requests from your Next.js Frontend
# In production, replace "*" with your actual Cloud Run Frontend URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "robotperizia-api"}

# Include Routers
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(tasks.router, prefix="/tasks", tags=["Cloud Tasks"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])