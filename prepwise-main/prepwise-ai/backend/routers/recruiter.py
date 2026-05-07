"""
PrepWise AI - Recruiter API router

This module exposes recruiter-only endpoints to:
- List candidates (real DB data, with mock fallback during demos)
- Filter candidates by score/role/skills
- View a full candidate profile (skills, session history, weaknesses, roadmap status)
- Produce a shortlist of top candidates matching threshold criteria

No frontend code belongs here; this file is backend-only and mounts endpoints
under the `/recruiter` prefix (later registered by `backend/main.py`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import InterviewSession, JobRole, SkillScore, User

# Create router instance for all recruiter endpoints.
router = APIRouter(prefix="/recruiter", tags=["recruiter"])


# ----------------------------
# Pydantic models (required)
# ----------------------------


class SkillScoreItem(BaseModel):
    """Per-skill claimed vs tested details."""

    claimed_level: Optional[str] = None
    tested_level: Optional[str] = None
    authenticity_gap: Optional[float] = None
    last_updated: Optional[datetime] = None


class SessionHistoryItem(BaseModel):
    """Summarized interview session history used in profiles."""

    started_at: datetime
    completed_at: Optional[datetime] = None
    target_role: Optional[str] = None
    overall_score: float  # normalized 0..1
    authenticity_score: float  # normalized 0..1
    readiness_score: float  # normalized 0..1


class WeaknessMap(BaseModel):
    """Skills with below-threshold tested proficiency (0..1)."""

    # Map: skill_name -> tested proficiency numeric (0..1)
    skills_below_threshold: Dict[str, float] = {}


class RoadmapCompletionStatus(BaseModel):
    """Simple roadmap completion status for demo UX."""

    completion_percent: float  # normalized 0..1
    status: str  # e.g., On Track / Needs Practice


class CandidateProfile(BaseModel):
    """
    Unified response schema for all recruiter endpoints.

    Endpoints return either:
    - List[CandidateProfile] (candidates/filter/shortlist)
    - CandidateProfile (candidates/{candidate_id})
    """

    candidate_id: int
    name: str
    email: EmailStr
    target_role: Optional[str] = None

    overall_score: float  # normalized 0..1
    authenticity_score: float  # normalized 0..1
    interview_count: int
    last_active: Optional[datetime] = None

    skill_scores: Dict[str, SkillScoreItem] = Field(default_factory=dict)
    status: str  # Verified / Developing / Overstated

    session_history: List[SessionHistoryItem] = Field(default_factory=list)
    weakness_map: Dict[str, float] = Field(default_factory=dict)  # skill_name -> tested numeric (0..1)
    roadmap_completion_status: RoadmapCompletionStatus = Field(
        default_factory=lambda: RoadmapCompletionStatus(
            completion_percent=0.0, status="Needs Practice"
        )
    )


# ----------------------------
# Mock data (required)
# ----------------------------

# Module-level constant list of mock candidates.
# These candidates include the same fields as real candidates so the response
# schema stays identical whether the DB is empty or not.
MOCK_CANDIDATES: List[CandidateProfile] = [
    CandidateProfile(
        candidate_id=1001,
        name="Aarav Mehta",
        email="aarav.mehta@demo.com",
        target_role="SDE-1",
        overall_score=0.74,
        authenticity_score=0.66,
        interview_count=2,
        last_active=datetime(2026, 5, 3, 10, 15, 0),
        skill_scores={
            "Python": SkillScoreItem(claimed_level="intermediate", tested_level="intermediate", authenticity_gap=0.0, last_updated=datetime(2026, 5, 2, 9, 0, 0)),
            "Data Structures": SkillScoreItem(claimed_level="intermediate", tested_level="intermediate", authenticity_gap=0.0, last_updated=datetime(2026, 5, 2, 9, 0, 0)),
            "REST APIs": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 5, 2, 9, 0, 0)),
            "System Design": SkillScoreItem(claimed_level="beginner", tested_level="beginner", authenticity_gap=0.0, last_updated=datetime(2026, 5, 2, 9, 0, 0)),
        },
        status="Verified",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 4, 28, 11, 0, 0),
                completed_at=datetime(2026, 4, 28, 11, 42, 0),
                target_role="SDE-1",
                overall_score=0.71,
                authenticity_score=0.63,
                readiness_score=0.69,
            ),
            SessionHistoryItem(
                started_at=datetime(2026, 5, 1, 12, 0, 0),
                completed_at=datetime(2026, 5, 1, 12, 38, 0),
                target_role="SDE-1",
                overall_score=0.77,
                authenticity_score=0.69,
                readiness_score=0.76,
            ),
        ],
        weakness_map={"REST APIs": 0.33, "System Design": 0.33},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.74, status="On Track"),
    ),
    CandidateProfile(
        candidate_id=1002,
        name="Diya Nair",
        email="diya.nair@demo.com",
        target_role="Frontend Developer",
        overall_score=0.61,
        authenticity_score=0.48,
        interview_count=1,
        last_active=datetime(2026, 5, 5, 17, 5, 0),
        skill_scores={
            "JavaScript": SkillScoreItem(claimed_level="intermediate", tested_level="intermediate", authenticity_gap=0.0, last_updated=datetime(2026, 5, 5, 16, 0, 0)),
            "React": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 5, 5, 16, 0, 0)),
            "CSS": SkillScoreItem(claimed_level="expert", tested_level="intermediate", authenticity_gap=10.0, last_updated=datetime(2026, 5, 5, 16, 0, 0)),
            "REST APIs": SkillScoreItem(claimed_level="beginner", tested_level="beginner", authenticity_gap=0.0, last_updated=datetime(2026, 5, 5, 16, 0, 0)),
        },
        status="Developing",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 5, 5, 15, 0, 0),
                completed_at=datetime(2026, 5, 5, 15, 55, 0),
                target_role="Frontend Developer",
                overall_score=0.61,
                authenticity_score=0.48,
                readiness_score=0.56,
            )
        ],
        weakness_map={"React": 0.33, "REST APIs": 0.33},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.61, status="In Progress"),
    ),
    CandidateProfile(
        candidate_id=1003,
        name="Kunal Sharma",
        email="kunal.sharma@demo.com",
        target_role="Data Engineer",
        overall_score=0.82,
        authenticity_score=0.73,
        interview_count=3,
        last_active=datetime(2026, 4, 30, 9, 40, 0),
        skill_scores={
            "Python": SkillScoreItem(claimed_level="expert", tested_level="expert", authenticity_gap=0.0, last_updated=datetime(2026, 4, 30, 9, 20, 0)),
            "SQL": SkillScoreItem(claimed_level="expert", tested_level="expert", authenticity_gap=0.0, last_updated=datetime(2026, 4, 30, 9, 20, 0)),
            "PostgreSQL": SkillScoreItem(claimed_level="expert", tested_level="intermediate", authenticity_gap=10.0, last_updated=datetime(2026, 4, 30, 9, 20, 0)),
            "Docker": SkillScoreItem(claimed_level="intermediate", tested_level="intermediate", authenticity_gap=0.0, last_updated=datetime(2026, 4, 30, 9, 20, 0)),
            "Kubernetes": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 4, 30, 9, 20, 0)),
        },
        status="Verified",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 4, 22, 10, 0, 0),
                completed_at=datetime(2026, 4, 22, 10, 48, 0),
                target_role="Data Engineer",
                overall_score=0.79,
                authenticity_score=0.71,
                readiness_score=0.80,
            ),
            SessionHistoryItem(
                started_at=datetime(2026, 4, 25, 11, 0, 0),
                completed_at=datetime(2026, 4, 25, 11, 42, 0),
                target_role="Data Engineer",
                overall_score=0.85,
                authenticity_score=0.76,
                readiness_score=0.84,
            ),
            SessionHistoryItem(
                started_at=datetime(2026, 4, 30, 9, 0, 0),
                completed_at=datetime(2026, 4, 30, 9, 35, 0),
                target_role="Data Engineer",
                overall_score=0.82,
                authenticity_score=0.73,
                readiness_score=0.81,
            ),
        ],
        weakness_map={"Kubernetes": 0.33},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.82, status="Completed"),
    ),
    CandidateProfile(
        candidate_id=1004,
        name="Meera Iyer",
        email="meera.iyer@demo.com",
        target_role="ML Engineer",
        overall_score=0.55,
        authenticity_score=0.39,
        interview_count=2,
        last_active=datetime(2026, 5, 2, 13, 10, 0),
        skill_scores={
            "Machine Learning": SkillScoreItem(claimed_level="expert", tested_level="intermediate", authenticity_gap=10.0, last_updated=datetime(2026, 5, 2, 12, 50, 0)),
            "Deep Learning": SkillScoreItem(claimed_level="expert", tested_level="beginner", authenticity_gap=20.0, last_updated=datetime(2026, 5, 2, 12, 50, 0)),
            "NLP": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 5, 2, 12, 50, 0)),
            "TensorFlow": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 5, 2, 12, 50, 0)),
        },
        status="Overstated",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 4, 26, 14, 0, 0),
                completed_at=datetime(2026, 4, 26, 14, 40, 0),
                target_role="ML Engineer",
                overall_score=0.53,
                authenticity_score=0.37,
                readiness_score=0.50,
            ),
            SessionHistoryItem(
                started_at=datetime(2026, 5, 2, 13, 0, 0),
                completed_at=datetime(2026, 5, 2, 13, 42, 0),
                target_role="ML Engineer",
                overall_score=0.55,
                authenticity_score=0.39,
                readiness_score=0.54,
            ),
        ],
        weakness_map={"Deep Learning": 0.33, "NLP": 0.33, "TensorFlow": 0.33},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.55, status="Needs Practice"),
    ),
    CandidateProfile(
        candidate_id=1005,
        name="Rohan Verma",
        email="rohan.verma@demo.com",
        target_role="SDE-1",
        overall_score=0.68,
        authenticity_score=0.57,
        interview_count=2,
        last_active=datetime(2026, 5, 1, 9, 20, 0),
        skill_scores={
            "Python": SkillScoreItem(claimed_level="intermediate", tested_level="intermediate", authenticity_gap=0.0, last_updated=datetime(2026, 5, 1, 9, 0, 0)),
            "Algorithms": SkillScoreItem(claimed_level="expert", tested_level="intermediate", authenticity_gap=10.0, last_updated=datetime(2026, 5, 1, 9, 0, 0)),
            "Data Structures": SkillScoreItem(claimed_level="intermediate", tested_level="intermediate", authenticity_gap=0.0, last_updated=datetime(2026, 5, 1, 9, 0, 0)),
            "System Design": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 5, 1, 9, 0, 0)),
        },
        status="Developing",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 4, 20, 10, 0, 0),
                completed_at=datetime(2026, 4, 20, 10, 45, 0),
                target_role="SDE-1",
                overall_score=0.64,
                authenticity_score=0.53,
                readiness_score=0.60,
            ),
            SessionHistoryItem(
                started_at=datetime(2026, 5, 1, 9, 0, 0),
                completed_at=datetime(2026, 5, 1, 9, 30, 0),
                target_role="SDE-1",
                overall_score=0.68,
                authenticity_score=0.57,
                readiness_score=0.66,
            ),
        ],
        weakness_map={"System Design": 0.33},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.68, status="On Track"),
    ),
    CandidateProfile(
        candidate_id=1006,
        name="Sahana Rao",
        email="sahana.rao@demo.com",
        target_role="Frontend Developer",
        overall_score=0.79,
        authenticity_score=0.61,
        interview_count=1,
        last_active=datetime(2026, 5, 4, 16, 25, 0),
        skill_scores={
            "JavaScript": SkillScoreItem(claimed_level="expert", tested_level="expert", authenticity_gap=0.0, last_updated=datetime(2026, 5, 4, 16, 0, 0)),
            "React": SkillScoreItem(claimed_level="expert", tested_level="intermediate", authenticity_gap=10.0, last_updated=datetime(2026, 5, 4, 16, 0, 0)),
            "CSS": SkillScoreItem(claimed_level="expert", tested_level="expert", authenticity_gap=0.0, last_updated=datetime(2026, 5, 4, 16, 0, 0)),
        },
        status="Verified",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 5, 4, 15, 0, 0),
                completed_at=datetime(2026, 5, 4, 15, 50, 0),
                target_role="Frontend Developer",
                overall_score=0.79,
                authenticity_score=0.61,
                readiness_score=0.77,
            )
        ],
        weakness_map={},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.79, status="Completed"),
    ),
    CandidateProfile(
        candidate_id=1007,
        name="Vikram Singh",
        email="vikram.singh@demo.com",
        target_role="Data Engineer",
        overall_score=0.43,
        authenticity_score=0.33,
        interview_count=1,
        last_active=datetime(2026, 4, 29, 8, 5, 0),
        skill_scores={
            "SQL": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 4, 29, 7, 55, 0)),
            "Python": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 4, 29, 7, 55, 0)),
            "Docker": SkillScoreItem(claimed_level="beginner", tested_level="beginner", authenticity_gap=0.0, last_updated=datetime(2026, 4, 29, 7, 55, 0)),
        },
        status="Overstated",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 4, 29, 7, 0, 0),
                completed_at=datetime(2026, 4, 29, 7, 35, 0),
                target_role="Data Engineer",
                overall_score=0.43,
                authenticity_score=0.33,
                readiness_score=0.40,
            )
        ],
        weakness_map={"SQL": 0.33, "Python": 0.33},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.43, status="Needs Practice"),
    ),
    CandidateProfile(
        candidate_id=1008,
        name="Ishita Kulkarni",
        email="ishita.kulkarni@demo.com",
        target_role="ML Engineer",
        overall_score=0.66,
        authenticity_score=0.52,
        interview_count=2,
        last_active=datetime(2026, 5, 3, 19, 0, 0),
        skill_scores={
            "Machine Learning": SkillScoreItem(claimed_level="intermediate", tested_level="intermediate", authenticity_gap=0.0, last_updated=datetime(2026, 5, 3, 18, 50, 0)),
            "NLP": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 5, 3, 18, 50, 0)),
            "PyTorch": SkillScoreItem(claimed_level="intermediate", tested_level="intermediate", authenticity_gap=0.0, last_updated=datetime(2026, 5, 3, 18, 50, 0)),
        },
        status="Developing",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 4, 27, 20, 0, 0),
                completed_at=datetime(2026, 4, 27, 20, 45, 0),
                target_role="ML Engineer",
                overall_score=0.62,
                authenticity_score=0.50,
                readiness_score=0.58,
            ),
            SessionHistoryItem(
                started_at=datetime(2026, 5, 3, 18, 0, 0),
                completed_at=datetime(2026, 5, 3, 18, 42, 0),
                target_role="ML Engineer",
                overall_score=0.66,
                authenticity_score=0.52,
                readiness_score=0.64,
            ),
        ],
        weakness_map={"NLP": 0.33},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.66, status="On Track"),
    ),
    CandidateProfile(
        candidate_id=1009,
        name="Arjun Reddy",
        email="arjun.reddy@demo.com",
        target_role="SDE-1",
        overall_score=0.58,
        authenticity_score=0.44,
        interview_count=1,
        last_active=datetime(2026, 5, 6, 11, 10, 0),
        skill_scores={
            "JavaScript": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 5, 6, 11, 0, 0)),
            "REST APIs": SkillScoreItem(claimed_level="intermediate", tested_level="beginner", authenticity_gap=10.0, last_updated=datetime(2026, 5, 6, 11, 0, 0)),
            "Algorithms": SkillScoreItem(claimed_level="beginner", tested_level="beginner", authenticity_gap=0.0, last_updated=datetime(2026, 5, 6, 11, 0, 0)),
        },
        status="Overstated",
        session_history=[
            SessionHistoryItem(
                started_at=datetime(2026, 5, 6, 10, 0, 0),
                completed_at=datetime(2026, 5, 6, 10, 35, 0),
                target_role="SDE-1",
                overall_score=0.58,
                authenticity_score=0.44,
                readiness_score=0.55,
            )
        ],
        weakness_map={"JavaScript": 0.33, "REST APIs": 0.33, "Algorithms": 0.33},
        roadmap_completion_status=RoadmapCompletionStatus(completion_percent=0.58, status="Needs Practice"),
    ),
]


# ----------------------------
# Auth dependency (required)
# ----------------------------


def require_recruiter_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Recruiter-only guard:
    - The JWT must be valid (handled by `get_current_user`)
    - The user role must be `recruiter`
    """

    user_role = getattr(current_user, "role", "candidate")  # Defensive fallback if column changes
    if user_role != "recruiter":
        raise HTTPException(status_code=403, detail="Recruiter access only.")
    return current_user


# ----------------------------
# Internal helpers (demo-friendly + schema-stable)
# ----------------------------


def _tested_level_to_numeric(tested_level: Optional[str]) -> float:
    """Map tested level bucket to a normalized 0..1 number for weakness detection."""

    level = (tested_level or "").lower().strip()
    if level == "beginner":
        return 0.33
    if level == "intermediate":
        return 0.66
    if level == "expert":
        return 1.0
    return 0.0


def _compute_status_from_authenticity(authenticity_score: float) -> str:
    """Return Verified / Developing / Overstated using authenticity thresholds."""

    if authenticity_score >= 0.6:
        return "Verified"
    if authenticity_score >= 0.45:
        return "Developing"
    return "Overstated"


def _build_real_candidates(db: Session) -> List[CandidateProfile]:
    """
    Build candidate profiles from real DB data.

    Requirement: use real SkillScore and InterviewSession when present.
    We only include candidates who have at least one completed InterviewSession.
    """

    completed = (
        db.query(User, JobRole, InterviewSession)
        .join(InterviewSession, InterviewSession.user_id == User.id)
        .join(JobRole, JobRole.id == InterviewSession.job_role_id)
        .filter(InterviewSession.status == "completed")
        .all()
    )

    if not completed:
        return []

    # Aggregate session data per candidate.
    agg: Dict[int, Dict[str, Any]] = {}
    candidate_ids = set()

    for user, job_role, session in completed:
        candidate_ids.add(user.id)
        bucket = agg.setdefault(
            user.id,
            {
                "candidate_id": user.id,
                "name": user.name,
                "email": user.email,
                "target_role": None,  # set from latest session
                "overall_scores": [],  # raw 0..100
                "authenticity_scores": [],  # raw 0..100
                "readiness_scores": [],  # raw 0..100
                "last_active": None,
                "session_history": [],
            },
        )

        overall_raw = float(session.overall_score or 0.0)
        auth_raw = float(session.authenticity_score or 0.0)
        ready_raw = float(session.readiness_score or 0.0)

        # Update history list (normalized values for API).
        bucket["session_history"].append(
            SessionHistoryItem(
                started_at=session.started_at,
                completed_at=session.completed_at,
                target_role=job_role.name if hasattr(job_role, "name") else None,
                overall_score=overall_raw / 100.0,
                authenticity_score=auth_raw / 100.0,
                readiness_score=ready_raw / 100.0,
            )
        )

        # Keep a consistent last_active and latest target_role.
        completed_at = session.completed_at or session.started_at
        if bucket["last_active"] is None or completed_at > bucket["last_active"]:
            bucket["last_active"] = completed_at
            bucket["target_role"] = job_role.name

        bucket["overall_scores"].append(overall_raw)
        bucket["authenticity_scores"].append(auth_raw)
        bucket["readiness_scores"].append(ready_raw)

    # Load SkillScore rows for these candidates.
    skill_rows = db.query(SkillScore).filter(SkillScore.user_id.in_(list(candidate_ids))).all()
    skill_by_candidate: Dict[int, Dict[str, SkillScoreItem]] = {cid: {} for cid in candidate_ids}

    for s in skill_rows:
        items = skill_by_candidate.setdefault(s.user_id, {})
        # If multiple entries exist for the same skill, keep the most recent.
        existing = items.get(s.skill_name)
        if existing is None or (existing.last_updated is None or (s.last_updated or datetime.min) > existing.last_updated):
            items[s.skill_name] = SkillScoreItem(
                claimed_level=s.claimed_level,
                tested_level=s.tested_level,
                authenticity_gap=float(s.authenticity_gap) if s.authenticity_gap is not None else None,
                last_updated=s.last_updated,
            )

    # Convert aggregates to CandidateProfile objects.
    candidates: List[CandidateProfile] = []
    for cid, bucket in agg.items():
        overall_avg = (sum(bucket["overall_scores"]) / max(1, len(bucket["overall_scores"]))) / 100.0
        auth_avg = (sum(bucket["authenticity_scores"]) / max(1, len(bucket["authenticity_scores"]))) / 100.0
        # readiness is not requested at list level, but roadmap can use overall.
        tested_scores = skill_by_candidate.get(cid, {})

        weakness_map: Dict[str, float] = {}
        for skill_name, score_item in tested_scores.items():
            numeric = _tested_level_to_numeric(score_item.tested_level)
            if numeric < 0.5:
                weakness_map[skill_name] = numeric

        roadmap_status = "Needs Practice"
        if overall_avg >= 0.8:
            roadmap_status = "Completed"
        elif overall_avg >= 0.65:
            roadmap_status = "On Track"
        elif overall_avg >= 0.5:
            roadmap_status = "In Progress"

        candidates.append(
            CandidateProfile(
                candidate_id=bucket["candidate_id"],
                name=bucket["name"],
                email=bucket["email"],
                target_role=bucket["target_role"],
                overall_score=float(overall_avg),
                authenticity_score=float(auth_avg),
                interview_count=len(bucket["overall_scores"]),
                last_active=bucket["last_active"],
                skill_scores=tested_scores,
                status=_compute_status_from_authenticity(float(auth_avg)),
                session_history=bucket["session_history"],
                weakness_map=weakness_map,
                roadmap_completion_status=RoadmapCompletionStatus(
                    completion_percent=float(overall_avg),
                    status=roadmap_status,
                ),
            )
        )

    return candidates


def _apply_filter(
    candidates: List[CandidateProfile],
    *,
    min_score: Optional[float],
    role: Optional[str],
    skills: Optional[List[str]],
    sort_by: str,
) -> List[CandidateProfile]:
    """Filter and sort candidates in-memory (works for both real and mock lists)."""

    filtered = candidates

    if min_score is not None:
        if min_score < 0 or min_score > 1:
            raise HTTPException(status_code=422, detail="min_score must be between 0 and 1.")
        filtered = [c for c in filtered if c.overall_score >= min_score]

    if role:
        if role.strip() == "":
            raise HTTPException(status_code=422, detail="role must be a non-empty string.")
        role_norm = role.strip().lower()
        filtered = [c for c in filtered if (c.target_role or "").lower() == role_norm]

    if skills:
        # Keep candidates that have at least one of the requested skills.
        skill_set = {s.lower().strip() for s in skills if s and s.strip()}
        filtered = [
            c for c in filtered if any((skill_name or "").lower() in skill_set for skill_name in c.skill_scores.keys())
        ]

    if sort_by == "score":
        filtered.sort(key=lambda c: c.overall_score, reverse=True)
    elif sort_by == "name":
        filtered.sort(key=lambda c: c.name.lower())
    elif sort_by == "last_active":
        # None values go last
        filtered.sort(key=lambda c: c.last_active or datetime.min, reverse=True)
    else:
        raise HTTPException(status_code=422, detail="Invalid sort_by. Use score/name/last_active.")

    return filtered


# ----------------------------
# Routes (required)
# ----------------------------


@router.get("/candidates", response_model=List[CandidateProfile])
def list_candidates(
    db: Session = Depends(get_db),
    _: User = Depends(require_recruiter_user),
) -> List[CandidateProfile]:
    """
    Return all candidates with:
    candidate_id, name, email, target_role, overall_score, skill_scores, interview_count,
    last_active, authenticity_score, status.
    """

    try:
        real_candidates = _build_real_candidates(db)
        # Fallback: only when the real list is empty (no mixing in a single response).
        if not real_candidates:
            return MOCK_CANDIDATES
        # Sort by overall_score descending by default.
        real_candidates.sort(key=lambda c: c.overall_score, reverse=True)
        return real_candidates
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates/filter", response_model=List[CandidateProfile])
def filter_candidates(
    min_score: Optional[float] = Query(None, description="0..1 overall score threshold"),
    role: Optional[str] = Query(None, description="Target role name to match"),
    skills: Optional[List[str]] = Query(None, description="Repeated query params: skills=Python&skills=React"),
    sort_by: str = Query("score", description="score / name / last_active"),
    db: Session = Depends(get_db),
    _: User = Depends(require_recruiter_user),
) -> List[CandidateProfile]:
    """Filter + sort candidates by overall_score / role / skills."""

    try:
        real_candidates = _build_real_candidates(db)
        if not real_candidates:
            candidates = MOCK_CANDIDATES
        else:
            candidates = real_candidates

        return _apply_filter(
            candidates,
            min_score=min_score,
            role=role,
            skills=skills,
            sort_by=sort_by,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates/{candidate_id}", response_model=CandidateProfile)
def get_candidate_profile(
    candidate_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_recruiter_user),
) -> CandidateProfile:
    """Return a full candidate profile including weakness map and roadmap completion."""

    try:
        real_candidates = _build_real_candidates(db)
        if not real_candidates:
            # Use mock only when there are no real candidates at all.
            for c in MOCK_CANDIDATES:
                if c.candidate_id == candidate_id:
                    return c
            raise HTTPException(status_code=404, detail="Candidate not found.")

        for c in real_candidates:
            if c.candidate_id == candidate_id:
                return c

        raise HTTPException(status_code=404, detail="Candidate not found.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shortlist", response_model=List[CandidateProfile])
def shortlist_candidates(
    top_n: int = Query(10, ge=1, le=50, description="Number of candidates to return"),
    db: Session = Depends(get_db),
    _: User = Depends(require_recruiter_user),
) -> List[CandidateProfile]:
    """
    Return top N candidates who meet:
    - overall_score >= 0.65
    - at least 1 completed session
    - authenticity_score >= 0.6
    """

    try:
        real_candidates = _build_real_candidates(db)
        if not real_candidates:
            candidates = MOCK_CANDIDATES
        else:
            candidates = real_candidates

        shortlisted = [
            c
            for c in candidates
            if c.overall_score >= 0.65
            and c.interview_count >= 1
            and c.authenticity_score >= 0.6
        ]
        shortlisted.sort(key=lambda c: (c.overall_score, c.authenticity_score), reverse=True)
        return shortlisted[:top_n]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


