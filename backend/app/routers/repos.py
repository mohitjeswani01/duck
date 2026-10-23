from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Repo, RepoFile
from app.schemas.repo import RepoConnectRequest, RepoConnectResponse, RepoFileContentOut, RepoFileOut, RepoOut
from app.services import file_tools
from app.services.file_tools import PathTraversalError
from app.services.github_client import (
    GithubClientError,
    GithubRateLimitError,
    GithubUnavailableError,
    InvalidRepoUrlError,
    RepoNotFoundError,
    RepoPrivateError,
    RepoTooLargeError,
)
from app.services.repo_service import connect_repo

router = APIRouter(prefix="/repos", tags=["repos"])

_ERROR_STATUS = {
    InvalidRepoUrlError: 422,
    RepoNotFoundError: 404,
    RepoPrivateError: 422,
    RepoTooLargeError: 422,
    GithubRateLimitError: 429,
    GithubUnavailableError: 503,
}


def _to_repo_out(repo: Repo) -> RepoOut:
    return RepoOut(
        id=str(repo.id),
        github_url=repo.github_url,
        owner=repo.owner,
        name=repo.name,
        default_branch=repo.default_branch,
    )


@router.get("", response_model=list[RepoOut])
async def list_repos(db: AsyncSession = Depends(get_db)) -> list[RepoOut]:
    """Lists connected repos."""
    result = await db.execute(select(Repo))
    repos = result.scalars().all()
    return [_to_repo_out(repo) for repo in repos]


@router.get("/{repo_id}", response_model=RepoOut)
async def get_repo(repo_id: UUID, db: AsyncSession = Depends(get_db)) -> RepoOut:
    """Phase 4 — the workspace top bar needs a single repo's owner/name/url
    from the session's repo_id; `GET /repos` only lists all of them."""
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found. Connect it first via POST /repos/connect.")
    return _to_repo_out(repo)


@router.post("/connect", response_model=RepoConnectResponse)
async def connect_repo_endpoint(
    body: RepoConnectRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepoConnectResponse:
    """Downloads (or reuses a fresh stored copy of) a public GitHub repo and
    stores its filtered text files, ready for the file tools to query."""
    try:
        result = await connect_repo(db, body.github_url, settings)
    except GithubClientError as exc:
        status_code = _ERROR_STATUS.get(type(exc), 502)
        raise HTTPException(status_code=status_code, detail=exc.friendly_message) from exc

    return RepoConnectResponse(
        repo=_to_repo_out(result.repo),
        file_count=result.file_count,
        total_size_bytes=result.total_size_bytes,
        languages=result.languages,
        reused_cached_copy=result.reused_cached_copy,
    )


@router.get("/{repo_id}/files", response_model=list[RepoFileOut])
async def list_repo_files(repo_id: UUID, db: AsyncSession = Depends(get_db)) -> list[RepoFileOut]:
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found. Connect it first via POST /repos/connect.")

    result = await db.execute(select(RepoFile).where(RepoFile.repo_id == repo_id).order_by(RepoFile.file_path))
    files = result.scalars().all()
    return [
        RepoFileOut(path=f.file_path, size_bytes=f.size_bytes, language=f.language, created_at=f.created_at)
        for f in files
    ]


@router.get("/{repo_id}/file-content", response_model=RepoFileContentOut)
async def get_repo_file_content(
    repo_id: UUID, path: str, db: AsyncSession = Depends(get_db)
) -> RepoFileContentOut:
    """Raw file content for the frontend's hypothesis-evidence snippet viewer
    — the only place the frontend needs actual file text, as opposed to the
    paths/sizes `GET /repos/{repo_id}/files` already returns."""
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found. Connect it first via POST /repos/connect.")

    try:
        content = await file_tools.get_raw_file_content(db, repo_id, path)
    except PathTraversalError as exc:
        raise HTTPException(status_code=422, detail=exc.friendly_message) from exc

    if content is None:
        raise HTTPException(status_code=404, detail=f"No file at '{path}' in this repo.")

    return RepoFileContentOut(path=path, content=content, total_lines=len(content.splitlines()))
