import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# ---------- Project-specific imports ----------
from app.database import init_db, get_session
from app.schemas import SessionCreate, CodeGenRequest, GitHubPushRequest
from app.services.session_service import (
    list_sessions,
    get_session_by_id,
    create_session,
    delete_session,
    rename_session,
)
from app.services.code_generator import generate_code_stream
from app.services.github_service import push_to_github
from app.logger import get_logger

logger = get_logger(__name__)

# ---------- App definition ----------
template_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(template_dir))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()
    yield
    # Shutdown (if needed)
    logger.info("Application shutting down.")


app = FastAPI(
    title="AI Code Manager Studio Pro v2",
    description="Full-stack AI-powered project planning & code generation",
    version="2.0.0",
    lifespan=lifespan,
)

# Mount static files
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Static files mounted from {static_dir}")
else:
    logger.warning("Static directory not found, skipping mount.")


# ---------- Global Exception Handler ----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception occurred.")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


# ---------- Helper: JSONResponse shortcut ----------
from fastapi.responses import JSONResponse


# ---------- Routes ----------

@app.get("/")
async def serve_index():
    """Serve the main SPA entry point."""
    index_path = template_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    raise HTTPException(status_code=404, detail="index.html not found")


# ---------- Session Management ----------

@app.get("/api/sessions")
async def api_list_sessions():
    """Return all existing sessions."""
    sessions = await list_sessions()
    return sessions  # FastAPI will serialize the list of dicts


@app.get("/api/session/{session_id}")
async def api_get_session(session_id: str):
    """Get a single session by its ID."""
    session = await get_session_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/api/analyze")
async def api_analyze(session_data: SessionCreate):
    """
    Analyze a project prompt and create a new session.
    Returns the session ID and initial analysis.
    """
    try:
        session = await create_session(session_data)
        return session
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze request")


@app.delete("/api/session/{session_id}")
async def api_delete_session(session_id: str):
    """Delete a session."""
    success = await delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


@app.put("/api/session/{session_id}/rename")
async def api_rename_session(session_id: str, rename_data: dict):
    """
    Rename a session. Expects JSON body with 'name' field.
    """
    new_name = rename_data.get("name")
    if not new_name:
        raise HTTPException(status_code=400, detail="Missing 'name' field")
    success = await rename_session(session_id, new_name)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session renamed", "new_name": new_name}


# ---------- Code Generation (SSE) ----------

@app.post("/api/generate-code")
async def api_generate_code(request: CodeGenRequest):
    """
    Stream generated code via Server-Sent Events.
    The client should handle text/event-stream responses.
    """
    session_id = request.session_id
    prompt = request.prompt
    if not session_id or not prompt:
        raise HTTPException(status_code=400, detail="session_id and prompt are required")

    # Check that session exists
    session = await get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream():
        try:
            async for chunk in generate_code_stream(session_id, prompt):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream error for session {session_id}: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- GitHub Push ----------

@app.post("/api/push-to-github")
async def api_push_to_github(push_request: GitHubPushRequest):
    """
    Push generated code to a GitHub repository.
    Expects session_id, repo_owner, repo_name, branch, commit_message.
    """
    try:
        result = await push_to_github(push_request)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub push failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to push to GitHub")


# ---------- Entry point ----------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # development only; remove in production
        log_level="info",
    )