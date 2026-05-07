"""
PrepWise AI - Resume upload & skill extraction routes

Phase 2 implements:
- POST /api/resume/upload: accept a PDF, store it in `uploads/`, extract text,
  and return extracted `{skill_name, claimed_level}` objects.
- GET  /api/resume/skills: return the latest extracted skills for the user.

Skill extraction uses:
- pdfminer.six to parse PDF text
- a hardcoded `SKILLS_DATABASE` (~100+ skills)
- regex heuristics to infer claimed proficiency near each matched skill

If extraction fails, a mock skills list is returned as fallback.
"""

import os  # Build safe filesystem paths
import re  # Skill/proficiency matching via regex
import time  # Add a unique suffix for saved filenames
from typing import List, Dict  # Types for extracted skills payload

import aiofiles  # Async file IO for saving uploaded PDFs
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile  # FastAPI upload helpers
import pdfplumber  # Extract raw text from PDF pages
from sqlalchemy.orm import Session  # SQLAlchemy session type

from auth import get_current_user  # JWT auth dependency
from database import get_db  # DB session dependency
from models import Resume, User  # ORM models

# Create router instance to register under /api in `main.py`.
router = APIRouter()  # Router for resume endpoints


# Hardcoded list of tech skills for matching extracted text.
# NOTE: This is intentionally large so hackathon demos have good coverage.
SKILLS_DATABASE: List[str] = [
    # Core languages / web
    "Python",
    "JavaScript",
    "TypeScript",
    "React",
    "Node.js",
    "Express.js",
    "Angular",
    "Vue.js",
    "HTML",
    "CSS",
    "Sass",
    "REST APIs",
    "GraphQL",
    "WebSockets",
    "Webpack",
    "Babel",
    "Jest",
    "Mocha",
    "Chai",
    "Jasmine",
    "Redux",
    "Next.js",
    "Redux Toolkit",
    "Tailwind CSS",
    "Bootstrap",
    "JSON",
    "AJAX",
    "Fetch API",
    # Backend / databases
    "SQL",
    "SQLite",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "DynamoDB",
    "Neo4j",
    "ORM",
    "SQLAlchemy",
    "Entity Framework",
    "Django",
    "Flask",
    "FastAPI",
    "Spring Boot",
    "Ruby on Rails",
    "Laravel",
    "Microservices",
    "RESTful Services",
    "System Design",
    "Authentication",
    "Authorization",
    "OAuth",
    "JWT",
    "OpenAPI",
    "Swagger",
    # Data / ML / NLP
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "Computer Vision",
    "Reinforcement Learning",
    "TensorFlow",
    "Keras",
    "PyTorch",
    "Scikit-learn",
    "XGBoost",
    "LightGBM",
    "CatBoost",
    "Pandas",
    "NumPy",
    "Data Analysis",
    "Data Visualization",
    "Feature Engineering",
    "Model Evaluation",
    "Time Series",
    "Statistics",
    "Probability",
    "Regression",
    "Classification",
    "Clustering",
    "Dimensionality Reduction",
    "Hyperparameter Tuning",
    "A/B Testing",
    # DevOps / cloud / tooling
    "Docker",
    "Kubernetes",
    "Helm",
    "CI/CD",
    "Git",
    "GitHub",
    "GitLab",
    "Bitbucket",
    "Linux",
    "Bash",
    "Shell Scripting",
    "AWS",
    "Azure",
    "Google Cloud",
    "EC2",
    "S3",
    "RDS",
    "Lambda",
    "CloudWatch",
    "IAM",
    "Terraform",
    "Ansible",
    "Nginx",
    "Apache",
    "Traefik",
    "Grafana",
    "Prometheus",
    "ELK Stack",
    "Logging",
    "Monitoring",
    # Algorithms / CS fundamentals
    "Algorithms",
    "Data Structures",
    "Big O Notation",
    "Dynamic Programming",
    "Recursion",
    "Sorting",
    "Searching",
    "Binary Search",
    "Two Pointers",
    "Greedy Algorithms",
    "Trees",
    "Graphs",
    "Stacks",
    "Queues",
    "Hash Tables",
    "Linked Lists",
    # Additional languages
    "Java",
    "C++",
    "C",
    "Go",
    "Rust",
    "Ruby",
    "PHP",
    # Productivity / testing
    "Unit Testing",
    "Integration Testing",
    "Test-Driven Development",
    "CI",
    "CD",
    "Agile",
    "Scrum",
    # ML/NLP libraries
    "spaCy",
    "NLTK",
    "Sentence Transformers",
    "Hugging Face",
    "Transformers",
    "PyMuPDF",
    "pdfminer.six",
    "spaCy Matcher",
    # Platform / architecture
    "Micro frontends",
    "Event-Driven Architecture",
    "Message Queues",
    "Kafka",
    "RabbitMQ",
    "Web Performance",
]


# Mock fallback skills used when PDF parsing or extraction fails.
MOCK_SKILLS: List[Dict[str, str]] = [
    {"skill_name": "Python", "claimed_level": "intermediate"},
    {"skill_name": "SQL", "claimed_level": "intermediate"},
    {"skill_name": "React", "claimed_level": "beginner"},
    {"skill_name": "Machine Learning", "claimed_level": "intermediate"},
    {"skill_name": "NLP", "claimed_level": "beginner"},
    {"skill_name": "Docker", "claimed_level": "beginner"},
    {"skill_name": "Kubernetes", "claimed_level": "beginner"},
    {"skill_name": "System Design", "claimed_level": "intermediate"},
]


def _infer_claimed_level(around_text: str) -> str:  # Infer beginner/intermediate/expert from nearby text
    lower = around_text.lower()  # Normalize snippet for case-insensitive matching
    if re.search(r"\b(expert|expertise|mastery)\b", lower):  # Detect explicit expert markers
        return "expert"  # Strongest proficiency
    if re.search(r"\b(advanced|proficient|strong)\b", lower):  # Detect advanced/proficient markers
        return "expert"  # Map advanced to expert bucket for scoring
    if re.search(r"\b(intermediate|proficient)\b", lower):  # Detect intermediate markers
        return "intermediate"  # Middle proficiency
    if re.search(r"\b(beginner|novice|entry[- ]level|familiar)\b", lower):  # Detect beginner markers
        return "beginner"  # Lowest proficiency
    return "intermediate"  # Default when we can't infer explicitly


def extract_skills_from_text(text: str) -> List[Dict[str, str]]:  # Extract claimed skills from resume text
    text_lower = text.lower()  # Lowercase for easier substring matching
    extracted: List[Dict[str, str]] = []  # Accumulate unique skills
    seen = set()  # Track already-added skills

    for skill in SKILLS_DATABASE:  # Iterate over each known skill
        skill_lower = skill.lower()  # Lowercase skill for substring checks
        idx = text_lower.find(skill_lower)  # Find first occurrence index for context window
        if idx == -1:  # If skill string isn't present in resume text
            continue  # Move to next skill

        if skill_lower in seen:  # Avoid duplicates (same skill matched multiple times)
            continue  # Skip duplicates

        start = max(0, idx - 120)  # Build context window before the skill mention
        end = min(len(text_lower), idx + 120)  # Build context window after the skill mention
        snippet = text[start:end]  # Slice the original text using computed indices

        claimed_level = _infer_claimed_level(snippet)  # Infer claimed level near the mention
        extracted.append({"skill_name": skill, "claimed_level": claimed_level})  # Add to output list
        seen.add(skill_lower)  # Mark skill as processed

    return extracted  # Return all extracted skill objects


def _uploads_dir() -> str:  # Compute the absolute path to the `uploads/` directory
    # backend/routers/resume.py -> backend/routers -> backend -> prepwise-ai
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # Repo root of `prepwise-ai`
    return os.path.join(project_root, "uploads")  # Absolute uploads folder path


@router.post("/resume/upload")  # POST /api/resume/upload
async def upload_resume(  # Handle resume PDF upload and extraction
    file: UploadFile = File(...),  # Uploaded PDF file
    db: Session = Depends(get_db),  # SQLAlchemy DB session
    current_user: User = Depends(get_current_user),  # Authenticated user
) -> dict:
    try:  # Wrap in try/except per your error handling rules
        if not file.filename or not file.filename.lower().endswith(".pdf"):  # Validate PDF extension
            return {"error": "Please upload a PDF resume."}  # Client error payload

        uploads_dir = _uploads_dir()  # Resolve uploads folder path
        os.makedirs(uploads_dir, exist_ok=True)  # Ensure uploads directory exists

        unique_suffix = int(time.time())  # Unique suffix for filename collision avoidance
        safe_name = os.path.basename(file.filename)  # Prevent path traversal by stripping directories
        saved_path = os.path.join(uploads_dir, f"user_{current_user.id}_{unique_suffix}_{safe_name}")  # Full file path

        content = await file.read()  # Read uploaded bytes into memory
        async with aiofiles.open(saved_path, "wb") as f:  # Open target file for async writing
            await f.write(content)  # Write bytes to disk

        extracted_parts = []  # Collect extracted page text fragments
        with pdfplumber.open(saved_path) as pdf:  # Open the saved PDF file
            for page in pdf.pages:  # Iterate through each page
                extracted_parts.append(page.extract_text() or "")  # Append page text or empty string
        extracted_text = "\n".join(extracted_parts)  # Merge page text into one string
        if not extracted_text.strip():  # If extraction returns empty/whitespace
            raise ValueError("PDF text extraction returned empty content.")  # Force fallback below

        extracted_skills = extract_skills_from_text(extracted_text)  # Extract skills from extracted text
        if not extracted_skills:  # If we matched nothing from the skill database
            raise ValueError("No skills matched from SKILLS_DATABASE.")  # Force fallback below

        resume = Resume(  # Create a new Resume record
            user_id=current_user.id,  # Associate resume with user
            filename=safe_name,  # Store original filename
            raw_text=extracted_text,  # Store extracted text for later extraction/debug
            extracted_skills=extracted_skills,  # Store claimed skills with levels
        )  # End Resume creation

        db.add(resume)  # Add resume to session
        db.commit()  # Persist to DB
        db.refresh(resume)  # Refresh for generated fields

        return {"skills": extracted_skills}  # Return extracted skills to frontend
    except Exception:  # Force fallback logic on any failure
        return {"skills": MOCK_SKILLS}  # Mock skills fallback for demo continuity


@router.get("/resume/skills")  # GET /api/resume/skills
def get_resume_skills(  # Return latest extracted skills for the current user
    db: Session = Depends(get_db),  # SQLAlchemy DB session
    current_user: User = Depends(get_current_user),  # Authenticated user
) -> dict:
    try:  # Wrap in try/except per your error handling rules
        resume = (  # Query the latest resume for the user
            db.query(Resume)  # Resume table
            .filter(Resume.user_id == current_user.id)  # Only resumes for this user
            .order_by(Resume.uploaded_at.desc())  # Most recently uploaded first
            .first()  # Take first record
        )  # End query chain

        if resume is None:  # If no resume exists yet
            return {"skills": []}  # Return empty list

        return {"skills": resume.extracted_skills or []}  # Return stored extracted skills JSON
    except Exception as e:  # Return error payload on failures
        return {"error": str(e)}  # Error object for frontend


