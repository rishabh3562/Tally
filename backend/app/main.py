"""
FastAPI application entry point for Personal Finance OS backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Personal Finance OS API",
    description="Intelligent bank statement ingestion, categorization & AI-powered insights",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(status_code=200, content={"status": "healthy"})


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Personal Finance OS API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running"
    }


# TODO: Add API route imports
# from app.api import auth, transactions, events, chat, uploads
# app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
# app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
# app.include_router(events.router, prefix="/api/events", tags=["events"])
# app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
# app.include_router(uploads.router, prefix="/api/upload", tags=["uploads"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
