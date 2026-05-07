"""
PrepWise AI - Authentication helpers

Phase 2 implements:
- JWT token creation/verification (24-hour expiry)
- bcrypt password hashing
- FastAPI dependency `get_current_user()` for protected endpoints
"""

import os  # Read environment variables for JWT secret configuration
from datetime import datetime, timedelta  # Compute JWT expiration timestamps
from typing import Optional  # Used for optional helper returns

from fastapi import Depends, HTTPException, status  # FastAPI auth utilities
from fastapi.security import OAuth2PasswordBearer  # Extract bearer token from requests
from jose import JWTError, jwt  # JWT encode/decode
from passlib.context import CryptContext  # Password hashing/verifying using bcrypt
from dotenv import load_dotenv
from sqlalchemy.orm import Session  # SQLAlchemy session type for dependency injection

from database import get_db  # Database session dependency
from models import User  # ORM user model

# Load values from backend/.env if available.
load_dotenv()

# Secret key used to sign/verify JWTs (supports both SECRET_KEY and JWT_SECRET_KEY).
JWT_SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY")  # Environment variable containing the JWT secret
if not JWT_SECRET_KEY:  # Fail fast if the secret is missing
    raise RuntimeError("SECRET_KEY (or JWT_SECRET_KEY) environment variable is required.")  # Clear error message

# JWT signing algorithm; kept as a constant for consistency.
JWT_ALGORITHM = "HS256"  # HMAC-SHA256 used with symmetric secret keys

# Access token expiry time: 24 hours.
ACCESS_TOKEN_EXPIRE_HOURS = 24  # Token lifetime in hours

# Password hashing context configured to use bcrypt.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # bcrypt hashing strategy

# OAuth2 bearer token extractor for FastAPI dependencies.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")  # Token URL used by Swagger UI


def get_password_hash(password: str) -> str:  # Convert plaintext password to a bcrypt hash
    return pwd_context.hash(password)  # Hash with configured bcrypt context


def verify_password(plain_password: str, hashed_password: str) -> bool:  # Check plaintext password against hash
    return pwd_context.verify(plain_password, hashed_password)  # Verify using bcrypt context


def create_access_token(subject: str) -> str:  # Create a signed JWT access token
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)  # Compute expiration time
    to_encode = {"exp": expire, "sub": subject}  # Standard JWT payload: exp + subject
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)  # Sign and return JWT string


def get_current_user(  # FastAPI dependency for retrieving the current authenticated user
    token: str = Depends(oauth2_scheme),  # Extract JWT from the Authorization header
    db: Session = Depends(get_db),  # Get a DB session for user lookup
) -> User:  # Return the authenticated User ORM object
    credentials_exception = HTTPException(  # Define a consistent auth error response
        status_code=status.HTTP_401_UNAUTHORIZED,  # 401 status indicates invalid/missing credentials
        detail="Could not validate credentials",  # Message used by clients
        headers={"WWW-Authenticate": "Bearer"},  # Hint to clients that Bearer auth is required
    )  # End HTTPException definition

    try:  # Attempt to decode and validate JWT
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])  # Decode JWT claims
        subject: Optional[str] = payload.get("sub")  # Extract subject from token
        if subject is None:  # If no subject claim exists, token is invalid for our purposes
            raise credentials_exception  # Raise consistent auth error
    except JWTError:  # Any JWT decoding/validation failure
        raise credentials_exception  # Convert to FastAPI HTTP exception

    user = db.query(User).filter(User.email == subject).first()  # Find user by email (subject)
    if user is None:  # If user no longer exists
        raise credentials_exception  # Raise consistent auth error

    return user  # Return the authenticated user to the route handler

