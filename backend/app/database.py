"""
Database configuration and session management for TokenMetric backend.
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

# Database URL from environment or default to PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/tokenmetric"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    poolclass=NullPool if os.getenv("TESTING") else None,
    echo=os.getenv("DEBUG", "false").lower() == "true",
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database sessions.

    Yields:
        Session: SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.
    """
    from .models import Base
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """
    Drop all database tables.
    """
    from .models import Base
    Base.metadata.drop_all(bind=engine)


def reset_db() -> None:
    """
    Reset database (drop and recreate).
    """
    drop_db()
    init_db()
