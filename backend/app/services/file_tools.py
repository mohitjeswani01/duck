"""The three file tools Gemini calls during investigation: list_files,
read_file, search_code. Every one of them reads only from the repo_files
table already populated by repo_service.connect_repo — never the real
filesystem, never GitHub again. Pure matching/formatting logic is factored
out of the DB-fetching async wrappers so it can be unit tested without a
database (see tests/test_file_tools.py).
"""
import asyncio
import fnmatch
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import FileRead, RepoFile
from app.schemas.events import DuckEvent, ToolCallEvent

EmitFn = Callable[[DuckEvent], Awaitable[None]]

_MAX_SEARCH_PATTERN_LENGTH = 200
_MAX_REGEX_LINE_LENGTH = 300
_MAX_DISPLAYED_LINE_LENGTH = 500


class FileToolError(Exception):
    def __init__(self, friendly_message: str) -> None:
        self.friendly_message = friendly_message
        super().__init__(friendly_message)


class PathTraversalError(FileToolError):
    pass


class FileNotFoundInRepoError(FileToolError):
    pass


class InvalidSearchPatternError(FileToolError):
    pass


@dataclass(frozen=True)
class StoredFile:
    path: str
    content: str
    size_bytes: int
    language: str


class FileEntry(BaseModel):
    path: str
    size_bytes: int
    language: str


class ListFilesResult(BaseModel):
    files: list[FileEntry]
    total_matches: int
    truncated: bool


class ReadFileResult(BaseModel):
    path: str
    content: str
    start_line: int
    end_line: int
    total_lines: int
    truncated: bool


class SearchMatch(BaseModel):
    path: str
    line_number: int
    context: str


class SearchCodeResult(BaseModel):
    matches: list[SearchMatch]
    total_matches: int
    truncated: bool
    timed_out: bool = False


def _validate_relative_path(path: str) -> None:
    if not path or path.startswith("/") or path.startswith("\\"):
        raise PathTraversalError("That path isn't valid — use a path relative to the repo root.")
    segments = path.replace("\\", "/").split("/")
    if ".." in segments or "" in segments:
        raise PathTraversalError("That path isn't valid — use a path relative to the repo root.")


def _matches_pattern(path: str, pattern: str) -> bool:
    if any(c in pattern for c in "*?["):
        return fnmatch.fnmatch(path, pattern)
    stripped = pattern.rstrip("/")
    return path == stripped or path.startswith(stripped + "/")


def list_files_pure(files: list[StoredFile], pattern: str | None, max_results: int) -> ListFilesResult:
    if pattern:
        matched = [f for f in files if _matches_pattern(f.path, pattern)]
    else:
        matched = list(files)

    matched.sort(key=lambda f: f.path)
    total = len(matched)
    limited = matched[:max_results]
    return ListFilesResult(
        files=[FileEntry(path=f.path, size_bytes=f.size_bytes, language=f.language) for f in limited],
        total_matches=total,
        truncated=total > max_results,
    )


def _numbered(lines: list[str], start_line: int) -> str:
    out = []
    for offset, line in enumerate(lines):
        if len(line) > _MAX_DISPLAYED_LINE_LENGTH:
            line = line[:_MAX_DISPLAYED_LINE_LENGTH] + "...[line truncated]"
        out.append(f"{start_line + offset:>5}\t{line}")
    return "\n".join(out)


def read_file_pure(
    files: list[StoredFile],
    path: str,
    start_line: int | None,
    end_line: int | None,
    max_lines: int,
) -> ReadFileResult:
    _validate_relative_path(path)

    match = next((f for f in files if f.path == path), None)
    if match is None:
        raise FileNotFoundInRepoError(f"No file at '{path}' in this repo.")

    lines = match.content.splitlines()
    total_lines = len(lines)

    if start_line is not None or end_line is not None:
        first = max(1, start_line or 1)
        last = min(total_lines, end_line or total_lines)
        selected = lines[first - 1 : last] if first <= total_lines else []
        return ReadFileResult(
            path=path,
            content=_numbered(selected, first),
            start_line=first,
            end_line=max(first - 1, last) if selected else first - 1,
            total_lines=total_lines,
            truncated=False,
        )

    if total_lines <= max_lines:
        return ReadFileResult(
            path=path, content=_numbered(lines, 1), start_line=1, end_line=total_lines,
            total_lines=total_lines, truncated=False,
        )

    truncated_lines = lines[:max_lines]
    return ReadFileResult(
        path=path,
        content=_numbered(truncated_lines, 1)
        + f"\n... [truncated: showing lines 1-{max_lines} of {total_lines} total]",
        start_line=1,
        end_line=max_lines,
        total_lines=total_lines,
        truncated=True,
    )


def _context_snippet(lines: list[str], line_index: int) -> str:
    start = max(0, line_index - 1)
    end = min(len(lines), line_index + 2)
    snippet_lines = []
    for i in range(start, end):
        text = lines[i]
        if len(text) > _MAX_DISPLAYED_LINE_LENGTH:
            text = text[:_MAX_DISPLAYED_LINE_LENGTH] + "...[truncated]"
        marker = ">" if i == line_index else " "
        snippet_lines.append(f"{marker}{i + 1:>5}\t{text}")
    return "\n".join(snippet_lines)


def search_code_pure(
    files: list[StoredFile],
    query: str,
    file_pattern: str | None,
    is_regex: bool,
    max_results: int,
) -> SearchCodeResult:
    if not query:
        raise InvalidSearchPatternError("Search query can't be empty.")
    if len(query) > _MAX_SEARCH_PATTERN_LENGTH:
        raise InvalidSearchPatternError("That search pattern is too long.")

    compiled: re.Pattern | None = None
    if is_regex:
        try:
            compiled = re.compile(query)
        except re.error as exc:
            raise InvalidSearchPatternError(f"That regular expression is invalid: {exc}") from exc

    candidates = [f for f in files if _matches_pattern(f.path, file_pattern)] if file_pattern else files

    matches: list[SearchMatch] = []
    total_matches = 0

    for file in candidates:
        lines = file.content.splitlines()
        for i, line in enumerate(lines):
            if compiled is not None:
                if len(line) > _MAX_REGEX_LINE_LENGTH:
                    continue
                found = compiled.search(line) is not None
            else:
                found = query in line

            if found:
                total_matches += 1
                if len(matches) < max_results:
                    matches.append(
                        SearchMatch(path=file.path, line_number=i + 1, context=_context_snippet(lines, i))
                    )

    return SearchCodeResult(matches=matches, total_matches=total_matches, truncated=total_matches > max_results)


async def _load_repo_files(db: AsyncSession, repo_id: uuid.UUID) -> list[StoredFile]:
    result = await db.execute(select(RepoFile).where(RepoFile.repo_id == repo_id))
    return [
        StoredFile(path=row.file_path, content=row.content, size_bytes=row.size_bytes, language=row.language)
        for row in result.scalars().all()
    ]


async def _record_file_read(db: AsyncSession, session_id: uuid.UUID, path: str, reason: str) -> None:
    db.add(FileRead(session_id=session_id, file_path=path, reason=reason))
    await db.commit()


def _cap_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [output truncated at {max_chars} characters]"


async def list_files(
    db: AsyncSession,
    repo_id: uuid.UUID,
    settings: Settings,
    pattern: str | None = None,
    session_id: uuid.UUID | None = None,
    emit: EmitFn | None = None,
) -> ListFilesResult:
    files = await _load_repo_files(db, repo_id)
    result = list_files_pure(files, pattern, settings.tool_list_files_max_results)

    if session_id is not None and emit is not None:
        await emit(ToolCallEvent(session_id=session_id, tool="list_files", detail=pattern or "(all files)"))

    return result


async def read_file(
    db: AsyncSession,
    repo_id: uuid.UUID,
    path: str,
    settings: Settings,
    start_line: int | None = None,
    end_line: int | None = None,
    session_id: uuid.UUID | None = None,
    emit: EmitFn | None = None,
) -> ReadFileResult:
    files = await _load_repo_files(db, repo_id)
    result = read_file_pure(files, path, start_line, end_line, settings.tool_read_file_max_lines)
    result.content = _cap_chars(result.content, settings.tool_output_max_chars)

    if session_id is not None:
        if emit is not None:
            await emit(ToolCallEvent(session_id=session_id, tool="read_file", detail=path))
        await _record_file_read(db, session_id, path, reason="read_file")

    return result


async def _search_with_timeout(
    files: list[StoredFile],
    query: str,
    file_pattern: str | None,
    is_regex: bool,
    max_results: int,
    timeout_seconds: float,
) -> SearchCodeResult:
    """Runs the (CPU-bound, potentially slow on a pathological regex) search in
    a worker thread with a wall-clock budget. A hung thread isn't killed — Python
    has no safe way to do that — but the event loop is freed immediately on
    timeout rather than blocking the request indefinitely."""
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, search_code_pure, files, query, file_pattern, is_regex, max_results),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        return SearchCodeResult(matches=[], total_matches=0, truncated=False, timed_out=True)


async def search_code(
    db: AsyncSession,
    repo_id: uuid.UUID,
    query: str,
    settings: Settings,
    file_pattern: str | None = None,
    is_regex: bool = False,
    session_id: uuid.UUID | None = None,
    emit: EmitFn | None = None,
) -> SearchCodeResult:
    files = await _load_repo_files(db, repo_id)
    result = await _search_with_timeout(
        files, query, file_pattern, is_regex, settings.tool_search_max_results, settings.tool_search_timeout_seconds
    )

    if session_id is not None:
        if emit is not None:
            await emit(ToolCallEvent(session_id=session_id, tool="search_code", detail=query))
        for match in result.matches[:10]:
            await _record_file_read(db, session_id, match.path, reason=f"search_code: {query}")

    return result
