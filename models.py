from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class AnalyzeRequest(BaseModel):
    """Request model for analyzing a project idea."""
    idea: str = Field(..., min_length=1, max_length=5000, description="The project idea or description to analyze")
    session_id: Optional[str] = Field(None, description="Optional session ID to associate the analysis")

    @validator("idea")
    def idea_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Idea cannot be empty or whitespace only")
        return v.strip()


class GenerateCodeRequest(BaseModel):
    """Request model for generating code based on analyzed plan."""
    plan_id: str = Field(..., description="The ID of the analyzed plan to generate code from")
    session_id: Optional[str] = Field(None, description="Optional session ID for tracking")
    language: str = Field("python", description="Target programming language")
    additional_instructions: Optional[str] = Field(None, max_length=2000, description="Extra instructions for code generation")

    @validator("language")
    def validate_language(cls, v):
        allowed = ["python", "javascript", "typescript", "java", "go", "rust", "csharp"]
        if v.lower() not in allowed:
            raise ValueError(f"Language must be one of: {allowed}")
        return v.lower()


class PushToGitHubRequest(BaseModel):
    """Request model for pushing generated code to GitHub."""
    session_id: str = Field(..., description="Session ID containing the generated code")
    repo_name: str = Field(..., min_length=1, max_length=100, description="Name of the GitHub repository to create/push to")
    repo_description: Optional[str] = Field("", max_length=500, description="Description of the repository")
    private: bool = Field(True, description="Whether the repository should be private")
    branch: str = Field("main", description="Branch to push to")
    commit_message: Optional[str] = Field("Initial commit from AI Code Manager Studio", max_length=200, description="Commit message")

    @validator("repo_name")
    def validate_repo_name(cls, v):
        import re
        if not re.match(r'^[\w.-]+$', v):
            raise ValueError("Repository name can only contain letters, numbers, hyphens, underscores, and dots")
        return v


class SessionRenameRequest(BaseModel):
    """Request model for renaming a session."""
    session_id: str = Field(..., description="ID of the session to rename")
    new_name: str = Field(..., min_length=1, max_length=200, description="New name for the session")

    @validator("new_name")
    def name_not_empty(cls, v):
        stripped = v.strip()
        if not stripped:
            raise ValueError("New name cannot be empty")
        return stripped


class AnalyzeResponse(BaseModel):
    """Response model for analysis operation."""
    session_id: str
    plan_id: str
    summary: str
    details: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GenerateCodeResponse(BaseModel):
    """Response model for code generation."""
    session_id: str
    plan_id: str
    files: List[Dict[str, str]]  # list of {filename: content}
    language: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PushToGitHubResponse(BaseModel):
    """Response model for GitHub push operation."""
    success: bool
    repo_url: Optional[str] = None
    commit_hash: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionRenameResponse(BaseModel):
    """Response model for session rename."""
    session_id: str
    old_name: str
    new_name: str
    success: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "2.0.0"
    uptime_seconds: Optional[float] = None