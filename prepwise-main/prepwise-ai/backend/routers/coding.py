"""
PrepWise AI - Coding test routes

Phase 2 implements:
- POST /api/coding/start: pick a coding problem based on skill level
- POST /api/coding/submit: execute Python code safely and score via tests
- GET  /api/coding/problems: list available problems

Evaluation logic:
- Require a single function named `solve` from user-submitted Python code.
- Run predefined test cases against `solve` and compute:
  Score = (test_cases_passed / total_test_cases) * 100
- If execution fails (or is deemed unsafe), fall back to a mock 60% score.
"""

import random  # Randomly select coding problems
import re  # Minimal sanitization helpers for unsafe code
from datetime import datetime  # Timestamps for submissions
from typing import Any, Dict, List, Tuple, Optional  # Typing helpers

from fastapi import APIRouter, Depends  # FastAPI routing and DI
from pydantic import BaseModel  # Request model validation
from sqlalchemy.orm import Session  # SQLAlchemy session type

from auth import get_current_user  # JWT dependency for protected routes
from database import get_db  # DB session dependency
from models import CodingTest, User  # ORM models

# Create the coding router to be registered under /api in `main.py`.
router = APIRouter()  # Router instance


PROBLEM_BANK: List[Dict[str, Any]] = [
    # ----------------------- Easy -----------------------
    {
        "title": "FizzBuzz",
        "difficulty": "Easy",
        "problem_description": "Given n, return a list of strings for numbers 1..n: 'Fizz' if divisible by 3, 'Buzz' if divisible by 5, 'FizzBuzz' if divisible by both; otherwise return the number as a string.",
        "starter_code": "def solve(n):\n    # Return list of strings for 1..n\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [3], "expected": ["1", "2", "Fizz"]},
            {"args": [5], "expected": ["1", "2", "Fizz", "4", "Buzz"]},
            {"args": [15], "expected": ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]},
        ],
    },
    {
        "title": "Palindrome Checker",
        "difficulty": "Easy",
        "problem_description": "Given a string s, return True if s is a palindrome (case-insensitive), else False.",
        "starter_code": "def solve(s):\n    # Return True/False\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": ["racecar"], "expected": True},
            {"args": ["RaceCar"], "expected": True},
            {"args": ["hello"], "expected": False},
        ],
    },
    {
        "title": "Reverse String",
        "difficulty": "Easy",
        "problem_description": "Given a string s, return the reversed string.",
        "starter_code": "def solve(s):\n    # Return reversed string\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": ["abcd"], "expected": "dcba"},
            {"args": ["a"], "expected": "a"},
            {"args": [""], "expected": ""},
        ],
    },
    {
        "title": "Binary Search",
        "difficulty": "Easy",
        "problem_description": "Given a sorted list arr and a target, return the index of target if found, else -1.",
        "starter_code": "def solve(arr, target):\n    # Return index or -1\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[1, 3, 5, 7, 9], 7], "expected": 3},
            {"args": [[1, 3, 5, 7, 9], 1], "expected": 0},
            {"args": [[1, 3, 5, 7, 9], 2], "expected": -1},
        ],
    },
    {
        "title": "Valid Parentheses",
        "difficulty": "Easy",
        "problem_description": "Given a string s containing parentheses '()[]{}', return True if it is valid (properly nested), else False.",
        "starter_code": "def solve(s):\n    # Return True/False\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": ["()"], "expected": True},
            {"args": ["()[]{}"], "expected": True},
            {"args": ["(]"], "expected": False},
        ],
    },
    # ----------------------- Medium -----------------------
    {
        "title": "Fibonacci (Nth)",
        "difficulty": "Medium",
        "problem_description": "Given n (>=0), return the nth Fibonacci number where fib(0)=0, fib(1)=1.",
        "starter_code": "def solve(n):\n    # Return nth Fibonacci\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [0], "expected": 0},
            {"args": [1], "expected": 1},
            {"args": [10], "expected": 55},
        ],
    },
    {
        "title": "Two Sum",
        "difficulty": "Medium",
        "problem_description": "Given nums and target, return a sorted list of the two indices whose values sum to target. Assume exactly one solution.",
        "starter_code": "def solve(nums, target):\n    # Return sorted indices [i, j]\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[2, 7, 11, 15], 9], "expected": [0, 1]},
            {"args": [[3, 2, 4], 6], "expected": [1, 2]},
            {"args": [[3, 3], 6], "expected": [0, 1]},
        ],
    },
    {
        "title": "Find Duplicates",
        "difficulty": "Medium",
        "problem_description": "Given an array nums, return a sorted list of all distinct numbers that appear at least twice.",
        "starter_code": "def solve(nums):\n    # Return sorted list of duplicates\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[1, 1, 2, 2, 3]], "expected": [1, 2]},
            {"args": [[1, 2, 3]], "expected": []},
            {"args": [[0, 0, 0]], "expected": [0]},
        ],
    },
    {
        "title": "Longest Common Prefix",
        "difficulty": "Medium",
        "problem_description": "Given a list of strings strs, return the longest common prefix string among all strings.",
        "starter_code": "def solve(strs):\n    # Return common prefix\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [["flower", "flow", "flight"]], "expected": "fl"},
            {"args": [["dog", "racecar", "car"]], "expected": ""},
            {"args": [["interview", "internet", "internal"]], "expected": "in"},
        ],
    },
    {
        "title": "Merge Sorted Arrays",
        "difficulty": "Medium",
        "problem_description": "Given two sorted lists a and b, return a single merged sorted list.",
        "starter_code": "def solve(a, b):\n    # Return merged sorted list\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[1, 3, 5], [2, 4, 6]], "expected": [1, 2, 3, 4, 5, 6]},
            {"args": [[1, 2], []], "expected": [1, 2]},
            {"args": [[], [0]], "expected": [0]},
        ],
    },
    # ----------------------- Hard -----------------------
    {
        "title": "Product of Array Except Self",
        "difficulty": "Hard",
        "problem_description": "Given nums, return an array where each element is the product of all numbers except itself. Use division-free approach.",
        "starter_code": "def solve(nums):\n    # Return products array\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[1, 2, 3, 4]], "expected": [24, 12, 8, 6]},
            {"args": [[-1, 1, 0, -3, 3]], "expected": [0, 0, 9, 0, 0]},
        ],
    },
    {
        "title": "Subarray Sum Equals K",
        "difficulty": "Hard",
        "problem_description": "Given nums and k, return the count of subarrays whose sum equals k.",
        "starter_code": "def solve(nums, k):\n    # Return count of subarrays summing to k\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[1, 1, 1], 2], "expected": 2},
            {"args": [[1, 2, 3], 3], "expected": 2},  # [1,2] and [3]
        ],
    },
    {
        "title": "Longest Increasing Subsequence (LIS)",
        "difficulty": "Hard",
        "problem_description": "Given nums, return the length of the longest strictly increasing subsequence.",
        "starter_code": "def solve(nums):\n    # Return LIS length\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[10, 9, 2, 5, 3, 7, 101, 18]], "expected": 4},
            {"args": [[0, 1, 0, 3, 2, 3]], "expected": 4},
        ],
    },
    {
        "title": "Maximum Subarray Sum",
        "difficulty": "Hard",
        "problem_description": "Given nums, return the maximum subarray sum (Kadane's algorithm).",
        "starter_code": "def solve(nums):\n    # Return maximum subarray sum\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[-2, 1, -3, 4, -1, 2, 1, -5, 4]], "expected": 6},
            {"args": [[1]], "expected": 1},
        ],
    },
    {
        "title": "Kth Largest Element",
        "difficulty": "Hard",
        "problem_description": "Given nums and k, return the kth largest element.",
        "starter_code": "def solve(nums, k):\n    # Return kth largest\n    pass\n",
        "entry_point": "solve",
        "test_cases": [
            {"args": [[3, 2, 1, 5, 6, 4], 2], "expected": 5},
            {"args": [[3, 2, 3, 1, 2, 4, 5, 5, 6], 4], "expected": 4},
        ],
    },
]


def _difficulty_from_skill_level(skill_level: str) -> str:  # Map claimed/tested skill level to coding difficulty
    level = (skill_level or "").lower()  # Normalize input
    if level == "beginner":  # Beginner -> easy
        return "Easy"  # Matches PROBLEM_BANK difficulty strings
    if level == "intermediate":  # Intermediate -> medium
        return "Medium"  # Matches PROBLEM_BANK difficulty strings
    return "Hard"  # Expert (or unknown) -> hard


def _select_problem(difficulty: str) -> Dict[str, Any]:  # Select one problem from the bank by difficulty
    candidates = [p for p in PROBLEM_BANK if p["difficulty"] == difficulty]  # Filter by difficulty
    if not candidates:  # Safety fallback
        return PROBLEM_BANK[0]  # Return first problem
    return random.choice(candidates)  # Random pick for demo variety


def _is_code_too_risky(user_code: str) -> bool:  # Very lightweight risk heuristics (demo-level)
    lowered = (user_code or "").lower()  # Normalize code
    banned_patterns = [  # Patterns we never want to execute in untrusted code
        "import os",  # OS access
        "import sys",  # System access
        "__import__",  # Dynamic import
        "open(",  # File access
        "subprocess",  # Process spawning
        "socket",  # Networking
        "requests",  # HTTP access (could be abused)
    ]
    return any(p in lowered for p in banned_patterns)  # Flag code as risky if any pattern matches


def _safe_builtins() -> Dict[str, Any]:  # Provide a restricted set of Python builtins for exec()
    return {  # Allow basic computation and data structures
        "range": range,
        "len": len,
        "enumerate": enumerate,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "sorted": sorted,
        "set": set,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "float": float,
        "int": int,
        "str": str,
        "bool": bool,
    }  # End builtins whitelist


def _run_tests(user_code: str, problem: Dict[str, Any]) -> Tuple[int, int, float]:  # Exec user code and compute score
    entry_point = problem.get("entry_point", "solve")  # Expected function name in user code
    test_cases = problem["test_cases"]  # Test cases list

    if _is_code_too_risky(user_code):  # If code looks unsafe, refuse execution
        total = len(test_cases)  # Total tests
        passed = int(total * 0.6)  # Simulate 60% score
        score = (passed / max(1, total)) * 100.0  # Score percentage
        return passed, total, score  # Return simulated results

    safe_globals = {"__builtins__": _safe_builtins()}  # Restrict builtins
    local_env: Dict[str, Any] = {}  # Isolated namespace for exec results

    exec(user_code, safe_globals, local_env)  # Execute user code within restricted environment

    solve_fn = local_env.get(entry_point)  # Get the required function from local environment
    if solve_fn is None:  # If required function is missing
        total = len(test_cases)  # Total tests
        passed = int(total * 0.6)  # Simulate 60% score
        score = (passed / max(1, total)) * 100.0  # Score percentage
        return passed, total, score  # Return simulated results

    passed = 0  # Count passed tests
    total = len(test_cases)  # Total number of tests

    for tc in test_cases:  # Iterate through each test case
        args = tc.get("args", [])  # Positional args for the function
        expected = tc.get("expected")  # Expected output
        try:  # Each test is isolated with try/except to avoid stopping early
            result = solve_fn(*args)  # Execute student solve with provided args
            if result == expected:  # Exact equality for deterministic problems
                passed += 1  # Increment passed counter
        except Exception:  # If a test execution fails, treat as failed
            pass  # Continue to next test

    score = (passed / max(1, total)) * 100.0  # Compute score per spec
    return passed, total, score  # Return test results


def _find_problem_by_title(problem_title: str) -> Optional[Dict[str, Any]]:  # Find a problem in the bank by title
    for p in PROBLEM_BANK:  # Iterate through the bank
        if p["title"] == problem_title:  # Titles are unique in this demo bank
            return p  # Found problem
    return None  # Not found


class CodingStartRequest(BaseModel):  # Validates coding start request
    skill_level: str  # beginner/intermediate/expert from the user skill claims or tested level
    session_id: Optional[int] = None  # Optional linked interview session id


@router.post("/coding/start")  # POST /api/coding/start
def start_coding(  # Start a coding test by selecting a problem
    payload: CodingStartRequest,  # Incoming request
    db: Session = Depends(get_db),  # DB session dependency (not always used for start)
    current_user: User = Depends(get_current_user),  # Authenticated user
) -> dict:
    try:  # Wrap per error handling rules
        difficulty = _difficulty_from_skill_level(payload.skill_level)  # Map skill to difficulty bucket
        problem = _select_problem(difficulty)  # Choose a random problem at that difficulty
        return {  # Return problem details for the frontend editor
            "problem_title": problem["title"],
            "problem_description": problem["problem_description"],
            "language": "python",
            "starter_code": problem["starter_code"],
            "difficulty": difficulty,
        }  # End response
    except Exception as e:  # Catch all failures
        return {"error": str(e)}  # Error payload


class CodingSubmitRequest(BaseModel):  # Validates coding submission request
    session_id: Optional[int] = None  # Optional linked interview session id
    problem_title: str  # Which problem the user solved
    language: str = "python"  # Programming language
    user_code: str  # The full user-submitted code


@router.post("/coding/submit")  # POST /api/coding/submit
def submit_coding(  # Execute the code and persist the scored result
    payload: CodingSubmitRequest,  # Incoming submission payload
    db: Session = Depends(get_db),  # DB session
    current_user: User = Depends(get_current_user),  # Authenticated user
) -> dict:
    try:  # Wrap per error handling rules
        if payload.language.lower() != "python":  # Only Python supported in this demo Phase 2
            return {"error": "Only Python submissions are supported in this demo."}  # Client error payload

        problem = _find_problem_by_title(payload.problem_title)  # Get the problem definition
        if problem is None:  # Validate problem exists
            return {"error": "Problem not found."}  # Client error payload

        passed, total, score = _run_tests(payload.user_code, problem)  # Run tests + compute score

        coding_test = CodingTest(  # Create CodingTest record
            user_id=current_user.id,  # Candidate user
            session_id=payload.session_id,  # Optional interview session linkage
            problem_title=problem["title"],  # Title
            problem_description=problem["problem_description"],  # Description
            language=payload.language,  # Language
            user_code=payload.user_code,  # Store submitted code for review/analytics
            test_cases_passed=passed,  # Passed count
            total_test_cases=total,  # Total test count
            score=score,  # Overall score
            submitted_at=datetime.utcnow(),  # Submission timestamp
        )  # End CodingTest creation

        db.add(coding_test)  # Persist
        db.commit()  # Transaction commit
        db.refresh(coding_test)  # Refresh

        return {  # Return scoring payload to frontend
            "score": score,
            "test_cases_passed": passed,
            "total_test_cases": total,
        }  # End response
    except Exception:  # Execution failures should not crash the API
        problem = _find_problem_by_title(getattr(payload, "problem_title", ""))  # Best-effort find for total tests
        total = len(problem["test_cases"]) if problem else 5  # Default total tests if missing
        passed = int(total * 0.6)  # Simulate 60% pass rate
        score = (passed / max(1, total)) * 100.0  # Compute score
        return {  # Fallback mock response per your rules
            "score": score,
            "test_cases_passed": passed,
            "total_test_cases": total,
            "warning": "Code execution failed; returning simulated score.",
        }  # End fallback response


@router.get("/coding/problems")  # GET /api/coding/problems
def list_problems() -> dict:  # List all available problems for selection in the UI
    try:  # Wrap per error handling rules
        return {  # Return a simplified list (frontend can display title/description)
            "problems": [
                {
                    "problem_title": p["title"],
                    "problem_description": p["problem_description"],
                    "difficulty": p["difficulty"],
                }
                for p in PROBLEM_BANK
            ]
        }  # End response
    except Exception as e:  # Catch failures
        return {"error": str(e)}  # Error payload


