from datetime import datetime

from pydantic import BaseModel


class RepoOut(BaseModel):
    id: str
    github_url: str
    owner: str
    name: str
    default_branch: str


class RepoConnectRequest(BaseModel):
    github_url: str


class RepoConnectResponse(BaseModel):
    repo: RepoOut
    file_count: int
    total_size_bytes: int
    languages: dict[str, int]
    reused_cached_copy: bool


class RepoFileOut(BaseModel):
    path: str
    size_bytes: int
    language: str
    created_at: datetime


class RepoFileContentOut(BaseModel):
    """Phase 4 — the frontend's hypothesis evidence chips need to show a code
    snippet when clicked; nothing previously exposed raw file content."""

    path: str
    content: str
    total_lines: int
