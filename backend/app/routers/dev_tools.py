"""Dev-only endpoints for curl-testing the three file tools directly against a
connected repo, bypassing the (not-yet-built) Gemini conversation loop.
Only registered when settings.enable_dev_tools is true — see app/main.py.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.services import file_tools
from app.services.file_tools import FileToolError, ListFilesResult, ReadFileResult, SearchCodeResult

router = APIRouter(prefix="/dev/tools", tags=["dev"])


class ListFilesRequest(BaseModel):
    repo_id: UUID
    pattern: str | None = None


class ReadFileRequest(BaseModel):
    repo_id: UUID
    path: str
    start_line: int | None = None
    end_line: int | None = None


class SearchCodeRequest(BaseModel):
    repo_id: UUID
    query: str
    file_pattern: str | None = None
    is_regex: bool = False


@router.post("/list_files", response_model=ListFilesResult)
async def dev_list_files(
    body: ListFilesRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ListFilesResult:
    try:
        return await file_tools.list_files(db, body.repo_id, settings, pattern=body.pattern)
    except FileToolError as exc:
        raise HTTPException(status_code=422, detail=exc.friendly_message) from exc


@router.post("/read_file", response_model=ReadFileResult)
async def dev_read_file(
    body: ReadFileRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ReadFileResult:
    try:
        return await file_tools.read_file(
            db, body.repo_id, body.path, settings, start_line=body.start_line, end_line=body.end_line
        )
    except FileToolError as exc:
        raise HTTPException(status_code=422, detail=exc.friendly_message) from exc


@router.post("/search_code", response_model=SearchCodeResult)
async def dev_search_code(
    body: SearchCodeRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SearchCodeResult:
    try:
        return await file_tools.search_code(
            db, body.repo_id, body.query, settings, file_pattern=body.file_pattern, is_regex=body.is_regex
        )
    except FileToolError as exc:
        raise HTTPException(status_code=422, detail=exc.friendly_message) from exc
