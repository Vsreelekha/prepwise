"""
PrepWise AI backend entrypoint.

This module wires all API routers, configures CORS for local demos, and exposes
basic health endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import analytics, auth, interview, recruiter, resume, roadmap, scoring

# Create the FastAPI app instance used by ASGI servers.
app = FastAPI(title="PrepWise AI Backend")

# Enable permissive CORS for local dev/demo environments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with API prefix.
app.include_router(auth.router, prefix="/api")
app.include_router(resume.router, prefix="/api")
app.include_router(interview.router, prefix="/api")
app.include_router(scoring.router, prefix="/api")
app.include_router(roadmap.router, prefix="/api")
app.include_router(recruiter.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")


@app.get("/")
def root() -> dict:
    """Root endpoint to quickly validate backend startup."""
    return {"status": "PrepWise AI backend running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

