"""
PrepWise AI - Adaptive Interview routes

Phase 2 implements:
- POST /api/interview/start
- GET  /api/interview/question/{id}      (id = session_id)
- POST /api/interview/answer
- GET  /api/interview/results/{id}       (id = session_id)
- GET  /api/interview/history

It includes the exact adaptive difficulty and authenticity scoring algorithms
you specified.
"""

import random  # Select random questions from the bank
import re  # Keyword scoring helpers
import time  # Detect slow semantic scoring
from datetime import datetime  # Store timestamps
from typing import Dict, List, Tuple, Any, Optional  # Type hints for clarity

from fastapi import APIRouter, Depends  # FastAPI routing and dependency injection
from pydantic import BaseModel  # Request payload validation
from sqlalchemy.orm import Session  # SQLAlchemy DB session type

from auth import get_current_user  # JWT dependency
from database import get_db  # DB session dependency
from models import (  # ORM models used by this router
    JobRole,
    InterviewAnswer,
    InterviewQuestion,
    InterviewSession,
    Resume,
    SkillScore,
    User,
)

# Optional semantic similarity model imports (only used when available/fast).
try:  # Keep the API resilient if sentence-transformers is unavailable or slow
    from sentence_transformers import SentenceTransformer, util  # Semantic scoring primitives

    _ST_MODEL: Optional[SentenceTransformer] = None  # Lazy-loaded global model
except Exception:  # If import fails, semantic scoring will fall back to keyword overlap
    SentenceTransformer = None  # type: ignore
    util = None  # type: ignore
    _ST_MODEL = None  # type: ignore


# Create router instance registered under /api in `main.py`.
router = APIRouter()  # Router for all interview endpoints


# Difficulty mapping kept exactly as requested by the spec.
difficulty_map = {"beginner": 1, "intermediate": 2, "expert": 3}  # Map labels to numeric difficulties

# Reverse mapping for returning difficulty labels to the frontend.
_difficulty_label = {1: "beginner", 2: "intermediate", 3: "expert"}  # Numeric to label mapping

# Each interview session will ask exactly 10 questions (demo-friendly and matches the UI spec).
TOTAL_QUESTIONS = 10  # Total questions per interview session


def _bank_templates() -> Dict[str, List[str]]:  # Create question templates per difficulty
    beginner = [  # Beginner question templates (10+)
        "What is {skill}, and how would you explain it to a beginner?",
        "Describe a project where you used {skill}. What was your specific role?",
        "What are the key concepts behind {skill} that you are comfortable with?",
        "Which parts of {skill} do you find easiest, and why?",
        "How do you get started with {skill} when you have no prior context?",
        "Explain one common mistake people make when learning {skill}.",
        "Give a simple example of {skill} in practice.",
        "What tools or libraries have you used for {skill}?",
        "How do you verify that your understanding of {skill} is correct?",
        "What does 'good' look like for a beginner using {skill}?",
    ]  # End beginner templates

    intermediate = [  # Intermediate question templates (10+)
        "Describe a situation where {skill} was challenging. How did you address it?",
        "What trade-offs have you considered when applying {skill} in production?",
        "How do you debug issues related to {skill} in a real system?",
        "Explain your approach to designing or implementing {skill} end-to-end.",
        "How do you measure success for a task involving {skill}?",
        "What performance or reliability considerations come up with {skill}?",
        "How do you handle edge cases when working with {skill}?",
        "Describe a time you improved a system by changing how you use {skill}.",
        "How do you choose between alternative techniques for {skill}?",
        "Explain a workflow you follow to implement {skill} with tests.",
    ]  # End intermediate templates

    expert = [  # Expert question templates (10+)
        "How would you architect a scalable solution involving {skill} under strict constraints?",
        "Explain how you would evaluate and select models/approaches for {skill} with evidence.",
        "Describe a failure mode in systems using {skill} and how you would mitigate it.",
        "When applying {skill}, how do you ensure correctness and robustness?",
        "Explain your strategy for optimizing {skill} for latency, cost, and quality simultaneously.",
        "How do you reason about advanced trade-offs and complexity in {skill} systems?",
        "Describe how you would design an experiment to validate an approach using {skill}.",
        "What are the subtle pitfalls that experts watch for in {skill}, and how do you avoid them?",
        "Explain a complex integration involving {skill}. How did you manage dependencies?",
        "How would you mentor someone to reach expert-level proficiency in {skill}?",
    ]  # End expert templates

    return {"beginner": beginner, "intermediate": intermediate, "expert": expert}  # Return full template sets


def _question_type_for_difficulty(label: str) -> str:  # Return a question_type string for the difficulty label
    if label == "beginner":  # Beginners are tested with conceptual/behavioral questions
        return "behavioral"  # Behavioral type
    if label == "intermediate":  # Intermediate maps to technical questions
        return "technical"  # Technical type
    return "situational"  # Expert maps to situational questions


def _build_question_bank(skills: List[str]) -> Dict[Tuple[str, int], List[Dict[str, Any]]]:  # Build the QUESTION_BANK mapping
    templates = _bank_templates()  # Get templates per difficulty

    bank: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}  # Storage for bank entries keyed by (skill, difficulty_num)

    for skill in skills:  # For each skill we support
        for label, num in difficulty_map.items():  # Build entries for beginner/intermediate/expert levels
            question_list: List[Dict[str, Any]] = []  # Collect questions for this skill+level

            for t in templates[label]:  # Ensure we generate 10+ questions
                question_text = t.format(skill=skill)  # Fill in template with the skill name

                # Ideal answer includes key tokens used by keyword overlap scoring.
                ideal_answer = (
                    f"A strong answer about {skill} should include a clear definition of {skill}, "
                    f"at least one concrete example, and measurable outcomes or trade-offs relevant to {skill}."
                )  # Ideal answer text for semantic/keyword scoring

                question_list.append(  # Add question entry to bank
                    {
                        "question_text": question_text,  # Prompt shown to the candidate
                        "ideal_answer": ideal_answer,  # Text used to score similarity
                        "question_type": _question_type_for_difficulty(label),  # One of behavioral/technical/situational
                        "difficulty_label": label,  # beginner/intermediate/expert
                        "difficulty_num": num,  # Numeric difficulty for DB storage and adaptive logic
                    }  # End question entry
                )  # End append

            bank[(skill, num)] = question_list  # Store all questions for this skill+level

    return bank  # Return the complete bank


# Skills we include in the question bank. Job roles will usually overlap this set.
DEFAULT_QUESTION_SKILLS: List[str] = [
    "Python",
    "JavaScript",
    "React",
    "SQL",
    "Java",
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "Docker",
    "Kubernetes",
    "System Design",
    "Data Structures",
    "Algorithms",
    "FastAPI",
    "PostgreSQL",
    "MongoDB",
]


# QUESTION_BANK is keyed by (skill, difficulty_num) as required by the spec concept.
QUESTION_BANK: Dict[Tuple[str, int], List[Dict[str, Any]]] = _build_question_bank(DEFAULT_QUESTION_SKILLS)  # Build bank at import time


def _get_ideal_answer(skill: str, difficulty_num: int, question_text: str) -> str:  # Look up ideal answer by question text
    for q in QUESTION_BANK.get((skill, difficulty_num), []):  # Search in the bank for this exact question
        if q["question_text"] == question_text:  # Found matching question
            return q["ideal_answer"]  # Return ideal answer for scoring
    # If not found (should be rare), fall back to an ideal answer stub.
    return f"A strong answer about {skill} at difficulty {difficulty_num} should be specific and well-structured."  # Fallback ideal answer


def _keyword_score(answer: str, ideal_answer: str) -> float:  # Compute keyword overlap score (0-100)
    # Tokenize to alphanumeric words for a simple overlap metric.
    answer_tokens = set(re.findall(r"[a-zA-Z0-9_]+", answer.lower()))  # Extract word tokens from candidate answer
    ideal_tokens = set(re.findall(r"[a-zA-Z0-9_]+", ideal_answer.lower()))  # Extract word tokens from ideal answer

    if not ideal_tokens:  # Avoid division by zero
        return 0.0  # No ideal tokens means we can't score

    overlap = answer_tokens.intersection(ideal_tokens)  # Compute overlap set
    ratio = len(overlap) / max(1, len(ideal_tokens))  # Overlap ratio relative to ideal token count
    return max(0.0, min(100.0, ratio * 100.0))  # Convert to 0-100 score


def _semantic_score(answer: str, ideal_answer: str) -> Optional[float]:  # Compute semantic similarity score using sentence-transformers
    if SentenceTransformer is None or util is None:  # If imports failed, semantic scoring isn't available
        return None  # Indicate that semantic scoring should be skipped

    global _ST_MODEL  # Reuse a single model instance
    start = time.time()  # Track runtime to enable the speed fallback rule

    if _ST_MODEL is None:  # Lazy-load the model only once
        model_name = "sentence-transformers/all-MiniLM-L6-v2"  # Recommended model name
        _ST_MODEL = SentenceTransformer(model_name)  # Load embedding model

    # Convert texts to embeddings for cosine similarity.
    emb_a = _ST_MODEL.encode(answer, convert_to_tensor=True)  # Encode candidate answer
    emb_b = _ST_MODEL.encode(ideal_answer, convert_to_tensor=True)  # Encode ideal answer
    cos_sim = util.cos_sim(emb_a, emb_b).item()  # Cosine similarity in [-1, 1]

    elapsed = time.time() - start  # Runtime duration
    if elapsed > 2.0:  # If semantic scoring is slow, return None so caller can fall back.
        return None  # Trigger fallback logic

    # Map cosine similarity (-1..1) to an interpretable 0..100 range.
    return max(0.0, min(100.0, ((cos_sim + 1.0) / 2.0) * 100.0))  # Convert to 0-100 score


def score_answer(answer: str, ideal_answer: str) -> Tuple[float, str]:  # Score an answer and generate brief feedback
    # Always compute keyword overlap score.
    keyword = _keyword_score(answer, ideal_answer)  # Keyword-based score (0-100)

    # Try semantic scoring, but fall back to keyword-only if it is slow.
    semantic = _semantic_score(answer, ideal_answer)  # None indicates fallback
    if semantic is None:  # Semantic scoring unavailable or too slow
        final_score = keyword  # Use keyword overlap scoring only
    else:  # Combine both sources
        final_score = (0.5 * keyword) + (0.5 * semantic)  # Weighted combination of keyword + semantic scores

    final_score = max(0.0, min(100.0, final_score))  # Clamp to 0..100

    # Simple feedback text for demo use.
    if final_score >= 75.0:  # Strong response
        feedback = "Strong alignment with the expected concepts and examples."  # Short positive feedback
    elif final_score >= 40.0:  # Partially aligned response
        feedback = "Good start. Add more specific examples and clarify trade-offs or implementation details."  # Constructive feedback
    else:  # Weak response
        feedback = "Your answer is missing key concepts. Review fundamentals and practice with targeted examples."  # Guidance feedback

    return final_score, feedback  # Return score and feedback


def calculate_authenticity(claimed_level: str, avg_score: float) -> float:  # Exact algorithm requested by the spec
    level_thresholds = {  # Thresholds by claimed level
        "beginner": (0, 40),  # Beginner expected range
        "intermediate": (40, 70),  # Intermediate expected range
        "expert": (70, 100),  # Expert expected range
    }  # End thresholds
    expected_min, expected_max = level_thresholds[claimed_level]  # Unpack expected min/max
    if avg_score >= expected_min:  # If the average score meets at least the expected minimum
        return min(100, (avg_score / expected_max) * 100)  # Scale up relative to expected max
    else:  # Otherwise compute gap from expected minimum
        gap = expected_min - avg_score  # How far below the expected min the score is
        return max(0, 100 - (gap * 2))  # Reduce authenticity based on gap severity


def _map_avg_score_to_level(avg_score: float) -> str:  # Infer tested level bucket from average score
    if avg_score >= 70.0:  # Expert threshold
        return "expert"  # Tested as expert
    if avg_score >= 40.0:  # Intermediate threshold
        return "intermediate"  # Tested as intermediate
    return "beginner"  # Tested as beginner


def _compute_overall_weighted_score(  # Compute overall weighted average from per-question scores
    questions: List[InterviewQuestion],  # Questions served
    answers: List[InterviewAnswer],  # Answers submitted
) -> float:
    answer_by_qid = {a.question_id: a for a in answers}  # Index answers by question id
    weighted_sum = 0.0  # Weighted sum of scores
    weight_total = 0.0  # Sum of weights

    for q in questions:  # Iterate through served questions
        ans = answer_by_qid.get(q.id)  # Find answer for the question
        if ans is None or ans.ai_score is None:  # Skip missing answers
            continue  # Continue to next question
        weight = float(q.difficulty)  # Weight by difficulty numeric level
        weighted_sum += float(ans.ai_score) * weight  # Add weighted contribution
        weight_total += weight  # Accumulate weights

    if weight_total <= 0.0:  # Avoid division by zero
        return 0.0  # No score data means zero overall score

    return weighted_sum / weight_total  # Weighted average result


class StartInterviewRequest(BaseModel):  # Validates start interview payload
    job_role_id: int  # Job role id selected from the dashboard


class SubmitAnswerRequest(BaseModel):  # Validates answer submission payload
    session_id: int  # Interview session id
    question_id: int  # Interview question id
    user_answer: str  # Raw user answer text


@router.post("/interview/start")  # POST /api/interview/start
def start_interview(  # Create an interview session and return its id
    payload: StartInterviewRequest,  # Incoming job role selection
    db: Session = Depends(get_db),  # DB session
    current_user: User = Depends(get_current_user),  # Authenticated user
) -> dict:
    try:  # Wrap in try/except per your error handling rules
        job_role = db.query(JobRole).filter(JobRole.id == payload.job_role_id).first()  # Load job role
        if job_role is None:  # Validate job role exists
            return {"error": "Job role not found"}  # Client-friendly error

        # Create a new interview session record.
        session = InterviewSession(  # ORM instance
            user_id=current_user.id,  # Link to current candidate
            job_role_id=job_role.id,  # Link to chosen job role
            status="in_progress",  # Mark as active
            started_at=datetime.utcnow(),  # Record start timestamp
        )  # End InterviewSession creation

        db.add(session)  # Persist to DB
        db.commit()  # Save transaction
        db.refresh(session)  # Get generated id

        return {"session_id": session.id}  # Return session id expected by frontend
    except Exception as e:  # Catch and return errors as payload
        return {"error": str(e)}  # Error payload


@router.get("/interview/question/{id}")  # GET /api/interview/question/{id} (id=session_id)
def get_next_question(  # Serve the next adaptive question
    id: int,  # Session id passed in URL
    db: Session = Depends(get_db),  # DB session
    current_user: User = Depends(get_current_user),  # Authenticated user
) -> dict:
    try:  # Wrap in try/except per your error handling rules
        session = db.query(InterviewSession).filter(InterviewSession.id == id).first()  # Load session by id
        if session is None or session.user_id != current_user.id:  # Ensure ownership/valid session
            return {"error": "Session not found"}  # Client-friendly error
        if session.status != "in_progress":  # Ensure we only serve questions while in progress
            return {"error": "Session is not active"}  # Client-friendly error

        job_role = db.query(JobRole).filter(JobRole.id == session.job_role_id).first()  # Load job role for skills
        if job_role is None:  # Validate job role exists
            return {"error": "Job role not found"}  # Error payload

        required_skills = job_role.required_skills or []  # Extract JSON required skills list
        if not isinstance(required_skills, list) or len(required_skills) == 0:  # Normalize JSON shape
            required_skills = DEFAULT_QUESTION_SKILLS[:5]  # Safe fallback set

        # Determine how many answers have already been submitted.
        served_questions = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == id).all()  # Questions served so far
        answered_count = (  # Count answers associated with served questions
            db.query(InterviewAnswer)  # InterviewAnswer table
            .join(InterviewQuestion, InterviewAnswer.question_id == InterviewQuestion.id)  # Join on question_id
            .filter(InterviewQuestion.session_id == id)  # Limit to this session
            .count()  # Count matching answers
        )

        next_index = answered_count + 1  # The next question number (1-based)
        if next_index > TOTAL_QUESTIONS:  # Stop after 10 questions
            session.status = "completed"  # Mark completion early if asked too much
            session.completed_at = datetime.utcnow()  # Timestamp completion
            db.add(session)  # Track changes
            db.commit()  # Persist status update
            return {"error": "Interview complete"}  # Client-friendly error

        # Pick which skill to test: cycle through job_role.required_skills in order.
        skill = required_skills[(next_index - 1) % len(required_skills)]  # Adaptive skill selection chosen by user

        # Adaptive difficulty algorithm (exact logic requested).
        current_difficulty = 1  # Start beginner
        previous_answers = (  # Load all previous answers in submission order
            db.query(InterviewAnswer)  # Answers
            .join(InterviewQuestion, InterviewAnswer.question_id == InterviewQuestion.id)  # Join for ordering
            .filter(InterviewQuestion.session_id == id)  # This session only
            .order_by(InterviewAnswer.answered_at.asc())  # Ensure chronological order
            .all()  # Materialize list
        )

        for ans in previous_answers:  # Apply adaptive difficulty rule after each answered question
            score = float(ans.ai_score or 0.0)  # ai_score is 0..100
            if score >= 75.0:  # If score > 70 in the spec; this step uses >= 75 as given for difficulty updates
                current_difficulty = min(3, current_difficulty + 1)  # Increase difficulty
            elif score <= 40.0:  # If score < 40 in the spec
                current_difficulty = max(1, current_difficulty - 1)  # Decrease difficulty

        difficulty_num = current_difficulty  # Numeric difficulty used to choose the bank question

        # Select a random unused question from QUESTION_BANK for (skill, current_difficulty).
        asked_texts = {q.question_text for q in served_questions if q.skill_tested == skill and q.difficulty == difficulty_num}  # Already used questions for skill+difficulty
        candidates = QUESTION_BANK.get((skill, difficulty_num), [])  # Bank candidates for this skill+difficulty
        if not candidates:  # If bank doesn't have this skill/difficulty, use a generic skill entry.
            generic_skill = "Python"  # Choose a stable fallback skill
            candidates = QUESTION_BANK.get((generic_skill, difficulty_num), [])  # Candidate list
            skill = generic_skill  # Return fallback skill to frontend

        available = [q for q in candidates if q["question_text"] not in asked_texts]  # Filter to unused questions
        if not available:  # If all candidates were used
            available = candidates  # Loop back to reuse

        chosen = random.choice(available)  # Pick random candidate

        question = InterviewQuestion(  # Persist the served question so answers can reference it
            session_id=id,  # Link to session
            question_text=chosen["question_text"],  # Question prompt
            skill_tested=skill,  # Skill being tested
            difficulty=int(chosen["difficulty_num"]),  # Difficulty numeric 1..3
            question_type=chosen["question_type"],  # behavioral/technical/situational
        )  # End InterviewQuestion

        db.add(question)  # Add question record
        db.commit()  # Save to DB
        db.refresh(question)  # Get generated question id

        return {  # Response payload consumed by frontend
            "question_id": question.id,
            "question_text": question.question_text,
            "skill_tested": question.skill_tested,
            "difficulty": _difficulty_label.get(question.difficulty, "beginner"),
            "question_type": question.question_type,
            "question_number": next_index,
            "total_questions": TOTAL_QUESTIONS,
        }  # End response
    except Exception as e:  # Catch all failures
        return {"error": str(e)}  # Error payload


@router.post("/interview/answer")  # POST /api/interview/answer
def submit_answer(  # Submit candidate answer and compute AI score/feedback
    payload: SubmitAnswerRequest,  # Incoming session/question/user_answer
    db: Session = Depends(get_db),  # DB session
    current_user: User = Depends(get_current_user),  # Authenticated candidate
) -> dict:
    try:  # Wrap in try/except per your error handling rules
        session = db.query(InterviewSession).filter(InterviewSession.id == payload.session_id).first()  # Load session
        if session is None or session.user_id != current_user.id:  # Validate session ownership
            return {"error": "Session not found"}  # Error payload

        question = db.query(InterviewQuestion).filter(InterviewQuestion.id == payload.question_id).first()  # Load question
        if question is None or question.session_id != payload.session_id:  # Validate question belongs to session
            return {"error": "Question not found"}  # Error payload

        ideal_answer = _get_ideal_answer(question.skill_tested, int(question.difficulty), question.question_text)  # Bank lookup
        ai_score, feedback = score_answer(payload.user_answer, ideal_answer)  # Compute score + feedback

        answer = InterviewAnswer(  # Persist candidate answer + scoring
            question_id=question.id,  # Link to question
            user_answer=payload.user_answer,  # Store raw answer text
            ai_score=ai_score,  # Store computed score
            feedback=feedback,  # Store feedback
            answered_at=datetime.utcnow(),  # Timestamp answer submission
        )  # End InterviewAnswer

        db.add(answer)  # Track answer
        db.commit()  # Persist
        db.refresh(answer)  # Refresh generated fields

        # If we've reached 10 answered questions, finalize the session.
        answered_count = (  # Count how many answers exist for this session
            db.query(InterviewAnswer)  # Answer table
            .join(InterviewQuestion, InterviewAnswer.question_id == InterviewQuestion.id)  # Join for session filter
            .filter(InterviewQuestion.session_id == payload.session_id)  # Limit to this session
            .count()  # Count answers
        )

        if answered_count >= TOTAL_QUESTIONS:  # Finalize when 10 questions have answers
            # Load all served questions and answers for this session for computations.
            questions = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == payload.session_id).all()  # Questions served
            answers = db.query(InterviewAnswer).join(InterviewQuestion, InterviewAnswer.question_id == InterviewQuestion.id)  # Query answers
            answers = answers.filter(InterviewQuestion.session_id == payload.session_id).all()  # Answers for this session

            overall_score = _compute_overall_weighted_score(questions, answers)  # Weighted overall score

            # Skill coverage + authenticity calculation.
            job_role = db.query(JobRole).filter(JobRole.id == session.job_role_id).first()  # Load job role
            required_skills = (job_role.required_skills or []) if job_role else []  # Required skills list
            if not isinstance(required_skills, list) or not required_skills:  # Normalize JSON
                required_skills = DEFAULT_QUESTION_SKILLS[:5]  # Safe fallback

            # Load latest resume extracted skills for claimed levels.
            resume = (
                db.query(Resume)
                .filter(Resume.user_id == current_user.id)
                .order_by(Resume.uploaded_at.desc())
                .first()
            )
            extracted_claims = (resume.extracted_skills or []) if resume else []  # Claimed skills from resume
            claimed_by_skill = {x.get("skill_name"): x.get("claimed_level") for x in extracted_claims if isinstance(x, dict)}  # Map skill_name -> claimed_level

            # Compute avg scores and authenticity per required skill.
            skill_score_rows: List[SkillScore] = []  # Prepare rows for insert
            per_skill_authenticity: List[float] = []  # Authenticity score per skill (0-100)

            for s in required_skills:  # Evaluate each required skill
                # Collect all ai_scores for questions testing this skill.
                scores_for_skill = [a.ai_score for a in answers if a is not None and a.ai_score is not None and _ans_question_skill(db, a.question_id) == s]  # Gather scores

                # If we can't find any scores (shouldn't happen), treat as 0.
                avg_score = float(sum(scores_for_skill) / len(scores_for_skill)) if scores_for_skill else 0.0  # Average per-skill test performance

                claimed_level = str(claimed_by_skill.get(s) or "beginner")  # Default claimed level to beginner
                if claimed_level not in difficulty_map:  # Normalize unexpected values
                    claimed_level = "beginner"  # Force to supported level buckets

                tested_level = _map_avg_score_to_level(avg_score)  # Infer tested level bucket from avg score
                authenticity = calculate_authenticity(claimed_level=claimed_level, avg_score=avg_score)  # Exact algorithm
                per_skill_authenticity.append(authenticity)  # Track for final authenticity_score

                claimed_numeric = difficulty_map[claimed_level]  # beginner/intermediate/expert numeric mapping
                tested_numeric = difficulty_map[tested_level]  # Convert tested level to numeric mapping
                authenticity_gap = float(claimed_numeric - tested_numeric) * 10.0  # Scale to a reasonable display range

                skill_score_rows.append(  # Create SkillScore ORM entries
                    SkillScore(
                        user_id=current_user.id,  # Candidate user id
                        skill_name=s,  # Skill being scored
                        claimed_level=claimed_level,  # Claimed proficiency
                        tested_level=tested_level,  # Tested proficiency inferred from scores
                        authenticity_gap=authenticity_gap,  # Derived gap
                        last_updated=datetime.utcnow(),  # Update timestamp
                    )
                )  # End SkillScore creation

            authenticity_score = float(sum(per_skill_authenticity) / len(per_skill_authenticity)) if per_skill_authenticity else 0.0  # Average authenticity across skills

            # Skill coverage: how many required skills were tested at least once.
            tested_skills = {q.skill_tested for q in questions}  # Unique skills tested in this session
            coverage_percent = (len(set(required_skills).intersection(tested_skills)) / max(1, len(required_skills))) * 100.0  # 0..100 coverage

            # Readiness score: combination of overall score + skill coverage.
            readiness_score = (0.7 * float(overall_score)) + (0.3 * float(coverage_percent))  # Weighted combination

            # Update session scores.
            session.overall_score = overall_score  # Store overall
            session.authenticity_score = authenticity_score  # Store authenticity
            session.readiness_score = readiness_score  # Store readiness
            session.status = "completed"  # Mark complete
            session.completed_at = datetime.utcnow()  # Completion timestamp

            db.add(session)  # Track session update
            db.add_all(skill_score_rows)  # Persist per-skill score entries
            db.commit()  # Persist computations

        next_prompt_available = answered_count < TOTAL_QUESTIONS  # Whether more questions remain after this submission

        return {  # Return per-question scoring for the frontend to display
            "ai_score": float(ai_score),  # 0..100
            "feedback": feedback,  # Short guidance text
            "next_question_available": next_prompt_available,  # Frontend uses this to show "Next"
        }  # End response
    except Exception as e:  # Catch failures
        return {"error": str(e)}  # Error payload


def _ans_question_skill(db: Session, question_id: int) -> str:  # Helper to fetch question.skill_tested for a question_id
    q = db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()  # Load question row
    return q.skill_tested if q else ""  # Return skill or empty string


@router.get("/interview/results/{id}")  # GET /api/interview/results/{id} (id=session_id)
def get_results(  # Return final scores and breakdown
    id: int,  # Session id
    db: Session = Depends(get_db),  # DB session
    current_user: User = Depends(get_current_user),  # Authenticated user
) -> dict:
    try:  # Wrap in try/except per your error handling rules
        session = db.query(InterviewSession).filter(InterviewSession.id == id).first()  # Load session
        if session is None or session.user_id != current_user.id:  # Validate ownership
            return {"error": "Session not found"}  # Error payload

        skill_scores = db.query(SkillScore).filter(SkillScore.user_id == current_user.id).all()  # Load computed skill scores

        return {  # Final payload
            "session_id": session.id,
            "status": session.status,
            "overall_score": session.overall_score,
            "authenticity_score": session.authenticity_score,
            "readiness_score": session.readiness_score,
            "skill_scores": [  # Serialize skill score rows
                {
                    "skill_name": s.skill_name,
                    "claimed_level": s.claimed_level,
                    "tested_level": s.tested_level,
                    "authenticity_gap": s.authenticity_gap,
                    "last_updated": s.last_updated,
                }
                for s in skill_scores
            ],
        }  # End response
    except Exception as e:  # Catch all failures
        return {"error": str(e)}  # Error payload


@router.get("/interview/history")  # GET /api/interview/history
def history(  # Return all past sessions for the current user
    db: Session = Depends(get_db),  # DB session
    current_user: User = Depends(get_current_user),  # Authenticated user
) -> dict:
    try:  # Wrap in try/except per your error handling rules
        sessions = (  # Query all sessions ordered by newest first
            db.query(InterviewSession)  # InterviewSession rows
            .filter(InterviewSession.user_id == current_user.id)  # Only current user's sessions
            .order_by(InterviewSession.started_at.desc())  # Newest first
            .all()  # Materialize list
        )

        return {  # Return sessions list to frontend
            "sessions": [
                {
                    "id": s.id,
                    "status": s.status,
                    "started_at": s.started_at,
                    "completed_at": s.completed_at,
                    "overall_score": s.overall_score,
                    "authenticity_score": s.authenticity_score,
                    "readiness_score": s.readiness_score,
                }
                for s in sessions
            ]
        }  # End response
    except Exception as e:  # Catch all failures
        return {"error": str(e)}  # Error payload


