"""
TokenMetric Backend API
Main application entry point with all routes and middleware.
"""

import os
import logging
from typing import Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from .database import init_db, get_db
from .blockchain import get_client
from .routes import vault, protocol, mobile
from .schemas import HealthResponse, ErrorResponse

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Version
VERSION = "1.0.0"

# Create FastAPI app
app = FastAPI(
    title="TokenMetric Backend",
    description="Backend API for TokenMetric vault protocol",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# =============================================================================
# Middleware
# =============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An internal error occurred",
            "details": {"message": str(exc)} if os.getenv("DEBUG") else None,
        },
    )


# =============================================================================
# Startup Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database and connections on startup."""
    # Initialize database tables
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    # Check blockchain connection
    try:
        client = get_client()
        if client.is_connected:
            logger.info(f"Connected to blockchain at block {client.latest_block}")
        else:
            logger.warning("Could not connect to blockchain RPC")
    except Exception as e:
        logger.warning(f"Blockchain connection check failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down TokenMetric backend")


# =============================================================================
# Include Routers
# =============================================================================

app.include_router(vault.router)
app.include_router(protocol.router)
app.include_router(mobile.router)


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check():
    """
    Comprehensive health check endpoint.

    Checks:
    - API status
    - Database connection
    - Blockchain RPC connection
    """
    db_status = "ok"
    blockchain_status = "ok"

    # Check database
    try:
        from sqlalchemy import text
        db = next(get_db())
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check blockchain
    try:
        client = get_client()
        if not client.is_connected:
            blockchain_status = "disconnected"
    except Exception as e:
        blockchain_status = f"error: {str(e)}"

    overall_status = "ok" if db_status == "ok" and blockchain_status == "ok" else "degraded"

    return HealthResponse(
        status=overall_status,
        version=VERSION,
        database=db_status,
        blockchain=blockchain_status,
    )


@app.get("/", tags=["root"])
def root():
    """Root endpoint with API information."""
    return {
        "name": "TokenMetric Backend",
        "version": VERSION,
        "status": "operational",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "vaults": "/vaults",
            "protocols": "/protocols",
            "mobile": "/mobile",
        },
    }


# =============================================================================
# Stats Endpoints
# =============================================================================

@app.get("/stats", tags=["stats"])
def global_stats():
    """Get global platform statistics."""
    from sqlalchemy import func
    from .models import Vault, User, Protocol

    db = next(get_db())

    total_vaults = db.query(func.count(Vault.id)).scalar()
    total_users = db.query(func.count(User.id)).scalar()
    total_protocols = db.query(func.count(Protocol.id)).scalar()

    total_tvl = db.query(func.sum(Vault.tvl)).scalar() or 0

    # Calculate 24h yield (mock for now)
    total_yield_24h = total_tvl * 0.001  # 0.1% daily yield approximation

    return {
        "total_vaults": total_vaults,
        "total_tvl": str(total_tvl),
        "total_users": total_users,
        "total_protocols": total_protocols,
        "total_yield_24h": str(total_yield_24h),
    }


# =============================================================================
# Error Response Helpers
# =============================================================================

def error_response(
    code: str,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Dict = None,
) -> JSONResponse:
    """Create standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=code,
            message=message,
            details=details,
        ).model_dump(),
    )
