"""
PrepWise AI - SQLAlchemy ORM models

Phase 2 defines the database schema used by the backend APIs. This includes
users, resumes, job roles, interview sessions/questions/answers, coding tests,
per-skill scoring, and recruiter views.
"""

from datetime import datetime  # Used for default timestamps

from sqlalchemy import Column  # Column type for SQLAlchemy
from sqlalchemy import DateTime  # DateTime column type
from sqlalchemy import Float  # Floating point for scores/gaps
from sqlalchemy import ForeignKey  # Foreign key constraints
from sqlalchemy import Integer  # Integer primary keys and numeric fields
from sqlalchemy import JSON  # JSON storage for extracted skills / required skills
from sqlalchemy import String  # Short text fields
from sqlalchemy import Text  # Longer text fields

from database import Base  # Shared declarative base from `database.py`


class User(Base):
    """User accounts (candidates and recruiters)."""

    __tablename__ = "users"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique user identifier
    email = Column(String, unique=True, index=True, nullable=False)  # Login email (unique)
    password_hash = Column(String, nullable=False)  # Bcrypt-hashed password
    name = Column(String, nullable=False)  # Display name
    role = Column(String, nullable=False, default="user")  # Either "user" or "recruiter"
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # Account creation timestamp


class Resume(Base):
    """Stored resume text and extracted skills for a user."""

    __tablename__ = "resumes"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique resume identifier
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Owner user id
    filename = Column(String, nullable=False)  # Original uploaded filename
    raw_text = Column(Text, nullable=True)  # Extracted resume text (plain text)
    extracted_skills = Column(JSON, nullable=True)  # Extracted skills as JSON payload
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # Upload timestamp


class JobRole(Base):
    """Job role definitions used to select interview question banks."""

    __tablename__ = "job_roles"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique job role identifier
    name = Column(String, unique=True, index=True, nullable=False)  # Role name (e.g., Backend Dev)
    required_skills = Column(JSON, nullable=True)  # List/dict of required skills (JSON)
    description = Column(Text, nullable=True)  # Free-form job description


class InterviewSession(Base):
    """A single adaptive interview session for a user and job role."""

    __tablename__ = "interview_sessions"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique interview session id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Candidate user id
    job_role_id = Column(Integer, ForeignKey("job_roles.id"), nullable=False, index=True)  # Job role id
    status = Column(String, nullable=False, default="in_progress")  # in_progress/completed
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # Session start timestamp
    completed_at = Column(DateTime, nullable=True)  # Session completion timestamp
    overall_score = Column(Float, nullable=True)  # Final overall score (0-100)
    authenticity_score = Column(Float, nullable=True)  # Skill authenticity score (0-100)
    readiness_score = Column(Float, nullable=True)  # Readiness score (0-100)


class InterviewQuestion(Base):
    """Questions served during an interview session."""

    __tablename__ = "interview_questions"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique question id
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, index=True)  # Parent session
    question_text = Column(Text, nullable=False)  # The question prompt text shown to the candidate
    skill_tested = Column(String, nullable=False, index=True)  # Skill the question tests
    difficulty = Column(Integer, nullable=False, default=1)  # 1/2/3 difficulty mapping
    question_type = Column(String, nullable=False, default="behavioral")  # behavioral/technical/situational


class InterviewAnswer(Base):
    """Candidate answers to interview questions along with scoring/feedback."""

    __tablename__ = "interview_answers"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique answer id
    question_id = Column(Integer, ForeignKey("interview_questions.id"), nullable=False, index=True)  # Parent question
    user_answer = Column(Text, nullable=False)  # Raw answer text provided by the user
    ai_score = Column(Float, nullable=True)  # Per-question AI score (0-100)
    feedback = Column(Text, nullable=True)  # Short AI feedback summary
    answered_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # Timestamp of answer submission


class CodingTest(Base):
    """Coding assessment run by a user (basic test case results)."""

    __tablename__ = "coding_tests"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique coding test id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Candidate user id
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=True, index=True)  # Optional linked interview session
    problem_title = Column(String, nullable=False)  # Title shown to user
    problem_description = Column(Text, nullable=True)  # Prompt/description
    language = Column(String, nullable=False, default="python")  # Submission language (Phase 2 may expand)
    user_code = Column(Text, nullable=True)  # Code submitted by the user
    test_cases_passed = Column(Integer, nullable=True)  # Number of passed test cases
    total_test_cases = Column(Integer, nullable=True)  # Total number of test cases
    score = Column(Float, nullable=True)  # Overall coding test score (0-100)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # Submission timestamp


class SkillScore(Base):
    """Per-skill claimed vs tested results used for authenticity scoring."""

    __tablename__ = "skill_scores"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique skill score id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Candidate user id
    skill_name = Column(String, nullable=False, index=True)  # Skill name being scored
    claimed_level = Column(String, nullable=True)  # Claimed proficiency level
    tested_level = Column(String, nullable=True)  # Tested proficiency level inferred from answers/tests
    authenticity_gap = Column(Float, nullable=True)  # Derived gap value (0-100 or similar)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)  # When this score was computed


class RecruiterView(Base):
    """Tracks that a recruiter viewed a specific candidate profile."""

    __tablename__ = "recruiter_views"  # SQL table name

    id = Column(Integer, primary_key=True, index=True)  # Unique view id
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Viewing recruiter user id
    candidate_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Viewed candidate user id
    viewed_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # Timestamp when viewed


