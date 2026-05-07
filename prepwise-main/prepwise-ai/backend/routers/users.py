"""
PrepWise AI - Users & Authentication routes

This module implements the authentication and profile endpoints required by
Phase 2:
- POST /api/auth/signup
- POST /api/auth/login
- GET  /api/users/me
- PUT  /api/users/me
"""

from typing import Optional  # Used for optional fields in request payloads

from fastapi import APIRouter, Depends  # FastAPI router and dependency helper
from pydantic import BaseModel, EmailStr  # Request validation types
from sqlalchemy.orm import Session  # SQLAlchemy session type

from auth import create_access_token, get_current_user, get_password_hash, verify_password  # Auth helpers
from database import get_db  # DB session dependency
from models import User  # ORM user model

# Create a dedicated router for auth/profile endpoints.
router = APIRouter()  # Router instance registered under /api in `main.py` later


class SignupRequest(BaseModel):  # Validates signup request payload
    email: EmailStr  # Email address for account login
    password: str  # Plain password provided by the user
    name: str  # Display name
    role: str = "user"  # Either "user" (candidate) or "recruiter"


class LoginRequest(BaseModel):  # Validates login request payload
    email: EmailStr  # Email address for login
    password: str  # Plain password provided by the user


class UpdateProfileRequest(BaseModel):  # Validates profile update payload
    name: Optional[str] = None  # Optional new display name
    password: Optional[str] = None  # Optional new password (bcrypt-hashed in DB)


@router.post("/auth/signup")  # POST /api/auth/signup
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> dict:  # Create a new user account
    try:  # Wrap in try/except per your error handling rules
        existing = db.query(User).filter(User.email == payload.email).first()  # Check if email is already registered
        if existing is not None:  # If user exists, reject signup
            return {"error": "Email already exists"}  # Client-friendly error payload

        user = User(  # Create the ORM user record
            email=payload.email,  # Store validated email
            password_hash=get_password_hash(payload.password),  # Store bcrypt hash (never plaintext)
            name=payload.name,  # Store display name
            role=payload.role,  # Store role
        )  # End user creation

        db.add(user)  # Add to the SQLAlchemy session
        db.commit()  # Persist transaction
        db.refresh(user)  # Load generated fields (e.g., id)

        return {  # Return a compact response for the frontend
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at,
        }  # End response
    except Exception as e:  # Catch all failures and return JSON error
        return {"error": str(e)}  # Return error payload


@router.post("/auth/login")  # POST /api/auth/login
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:  # Authenticate and return JWT
    try:  # Wrap in try/except per your error handling rules
        user = db.query(User).filter(User.email == payload.email).first()  # Find user by email
        if user is None:  # If no user exists, reject login
            return {"error": "Invalid email or password"}  # Client-friendly error

        if not verify_password(payload.password, user.password_hash):  # Validate password against bcrypt hash
            return {"error": "Invalid email or password"}  # Avoid leaking which field failed

        token = create_access_token(subject=user.email)  # Create JWT with subject set to email

        return {  # Return token payload expected by the frontend
            "access_token": token,
            "token_type": "bearer",
        }  # End token response
    except Exception as e:  # Catch all failures
        return {"error": str(e)}  # Return error payload


@router.get("/users/me")  # GET /api/users/me
def me(current_user: User = Depends(get_current_user)) -> dict:  # Return the current user's profile
    try:  # Wrap in try/except per your error handling rules
        return {  # Serialize ORM fields into JSON
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role,
            "created_at": current_user.created_at,
        }  # End response
    except Exception as e:  # Catch failures
        return {"error": str(e)}  # Return error payload


@router.put("/users/me")  # PUT /api/users/me
def update_me(  # Update the current user profile
    payload: UpdateProfileRequest,  # Incoming validated payload
    db: Session = Depends(get_db),  # DB session
    current_user: User = Depends(get_current_user),  # Currently authenticated user
) -> dict:
    try:  # Wrap in try/except per your error handling rules
        user = db.query(User).filter(User.id == current_user.id).first()  # Re-fetch the ORM object
        if user is None:  # If user missing, treat as auth/profile failure
            return {"error": "User not found"}  # Client-friendly error

        if payload.name is not None:  # Update name when provided
            user.name = payload.name  # Persist new name

        if payload.password is not None:  # Update password when provided
            user.password_hash = get_password_hash(payload.password)  # Persist bcrypt hash

        db.add(user)  # Ensure the ORM object is tracked
        db.commit()  # Persist updates
        db.refresh(user)  # Reload updated fields

        return {  # Return the updated profile
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at,
        }  # End response
    except Exception as e:  # Catch all failures
        return {"error": str(e)}  # Return error payload


