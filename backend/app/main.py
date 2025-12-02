import os
from dotenv import load_dotenv

load_dotenv()

from app.core.logger import setup_logging

# Setup Structured Logging
logger = setup_logging()
logger.info("Starting RobotPerizia API...")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import lifespan
from app.core.config import settings
# Import routers
from app.api.v1 import cases, tasks, auth, users, admin

app = FastAPI(
    title="RobotPerizia API",
    lifespan=lifespan # Connects the DB on startup
)

# CORS: Allow requests from your Next.js Frontend
# In production, replace "*" with your actual Cloud Run Frontend URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "robotperizia-api"}

# Include Routers
app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
app.include_router(tasks.router, prefix="/tasks", tags=["Cloud Tasks"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])