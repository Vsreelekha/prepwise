from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import SkillScore, InterviewSession, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/health")
def analytics_health() -> dict:
    return {"status": "analytics router ready"}

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)
@router.get("/insights")
def insights():

    return {
        "overall_score":85,
        "skills":[
            {
                "skill":"Python",
                "level":"Intermediate"
            }
        ]
    }

@router.get("/insights")
def get_insights():

    return {
        "overall_score": 85,
        "readiness_score": 78,
        "authenticity_score": 90,

        "insights":[
            {
                "skill":"Python",
                "claimed_level":"Expert",
                "tested_level":"Intermediate",
                "recommendation":"Practice APIs and OOP",

                "resources":[
                    {
                        "title":"Python Roadmap",
                        "url":"https://roadmap.sh/python"
                    }
                ]
            }
        ]
    }

LEARNING_RESOURCES = {
    "Python": [
        {
            "title": "Python Full Course",
            "url": "https://www.freecodecamp.org/learn"
        },
        {
            "title": "Python Roadmap",
            "url": "https://roadmap.sh/python"
        }
    ],

    "React": [
        {
            "title": "React Docs",
            "url": "https://react.dev"
        },
        {
            "title": "Frontend Roadmap",
            "url": "https://roadmap.sh/frontend"
        }
    ],

    "Machine Learning": [
        {
            "title": "Andrew NG ML Course",
            "url": "https://coursera.org"
        },
        {
            "title": "ML Roadmap",
            "url": "https://roadmap.sh/ai-data-scientist"
        }
    ],

    "System Design": [
        {
            "title": "System Design Roadmap",
            "url": "https://roadmap.sh/system-design"
        }
    ]
}


@router.get("/insights")
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    skill_scores = db.query(SkillScore).filter(
        SkillScore.user_id == current_user.id
    ).all()

    latest_session = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.started_at.desc())
        .first()
    )

    insights = []

    for skill in skill_scores:

        recommendation = ""

        if skill.tested_level == "beginner":
            recommendation = f"Practice beginner to intermediate concepts in {skill.skill_name}"

        elif skill.tested_level == "intermediate":
            recommendation = f"Build advanced projects using {skill.skill_name}"

        else:
            recommendation = f"You are strong in {skill.skill_name}"

        insights.append({
            "skill": skill.skill_name,
            "claimed_level": skill.claimed_level,
            "tested_level": skill.tested_level,
            "authenticity_gap": skill.authenticity_gap,
            "recommendation": recommendation,
            "resources": LEARNING_RESOURCES.get(skill.skill_name, [])
        })

    return {
        "overall_score": latest_session.overall_score if latest_session else 0,
        "readiness_score": latest_session.readiness_score if latest_session else 0,
        "authenticity_score": latest_session.authenticity_score if latest_session else 0,
        "insights": insights
    }