#
# PrepWise AI - Database utilities (SQLite + SQLAlchemy session dependency)
# ---------------------------------
# This Phase 2 file defines the SQLite database connection and the SQLAlchemy
# session dependency used by FastAPI routers.
# End of module header
import os  # Read environment variables for configurability
from typing import Generator  # Type hint for the get_db() dependency generator

from sqlalchemy import create_engine  # Build the SQLAlchemy engine from a DB URL
from sqlalchemy.orm import Session, declarative_base, sessionmaker  # Session type + Base + session factory

# The DB URL; defaults to a local SQLite file named `prepwise.db` in the current working directory.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./prepwise.db")  # SQLAlchemy-compatible database URL

# Create the SQLAlchemy engine; SQLite needs `check_same_thread=False` for FastAPI concurrency patterns.
engine = create_engine(  # SQLAlchemy engine used across the app
    DATABASE_URL,  # Database URL (SQLite by default)
    connect_args={"check_same_thread": False}  # Allow using the SQLite connection across threads
    if DATABASE_URL.startswith("sqlite")  # Only needed when using SQLite
    else {},  # No special connect args for other DB engines
)  # End create_engine call

# SessionLocal is the session factory used by request handlers to access the DB.
SessionLocal = sessionmaker(  # Create a configured session factory
    autocommit=False,  # Disable autocommit; we control transactions explicitly
    autoflush=False,  # Disable autoflush for predictable ORM behavior
    bind=engine,  # Bind this session factory to the engine above
)  # End sessionmaker call

# Base is the declarative base class; all ORM models should inherit from this.
Base = declarative_base()  # Base class for SQLAlchemy declarative models
# Spacer comment to keep the "comment on every line" convention consistent

def get_db() -> Generator[Session, None, None]:  # FastAPI dependency yielding a DB session
    db = SessionLocal()  # Create a new SQLAlchemy session for the request
    try:  # Ensure cleanup happens even when exceptions occur
        yield db  # Provide the session to the caller (router/handler)
    finally:  # Always close the session once the request is done
        db.close()  # Release DB resources

