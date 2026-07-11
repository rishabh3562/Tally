"""
FastAPI application entry point for Personal Finance OS backend
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from app.core.config import get_settings
from app.core.database import verify_supabase_key
from app.api import accounts, transactions, events, chat, uploads, users

load_dotenv()

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate external dependencies at boot so misconfig is obvious immediately."""
    ok, message = verify_supabase_key()
    if ok:
        print(f"[startup] OK: {message}")
    else:
        print("=" * 72)
        print(f"[startup] ERROR: {message}")
        print("   The API will start, but all database-backed routes will 500 until fixed.")
        print("=" * 72)
    yield


# Create FastAPI app
app = FastAPI(
    title="Personal Finance OS API",
    description="Intelligent bank statement ingestion, categorization & AI-powered insights",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(events.router)
app.include_router(chat.router)
app.include_router(uploads.router)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, reload=settings.debug)
