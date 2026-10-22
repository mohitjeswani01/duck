"""Fetches a public GitHub repo as a single tarball and extracts it into
filtered, stored text files. No per-file API calls and no code search API —
both are slow/rate-limited in ways that would break a live demo. Everything
list/read/search needs after this point comes from Postgres, not GitHub.
"""
import io
import re
import tarfile
from dataclasses import dataclass

import httpx

from app.config import Settings

GITHUB_URL_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)/"
    r"(?P<repo>[A-Za-z0-9_.-]+?)"
    r"(?:\.git)?/?$"
)

_SKIP_DIRS = {
    "node_modules", "dist", "build", ".next", ".git", "vendor",
    ".venv", "venv", "__pycache__", ".cache", ".turbo", "coverage",
    ".pytest_cache", "target", ".idea", ".vscode", "out", ".parcel-cache",
}

_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp", ".svg", ".avif",
    ".pdf", ".zip", ".gz", ".tar", ".tgz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".jar", ".pyc", ".o", ".a",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".mov", ".wav", ".avi", ".webm",
}

_SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "pnpm-lock.yml",
    "Pipfile.lock", "poetry.lock", "composer.lock", "Cargo.lock", "Gemfile.lock",
}

_LANGUAGE_BY_EXTENSION = {
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".py": "Python", ".rb": "Ruby", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++",
    ".cs": "C#", ".php": "PHP", ".swift": "Swift",
    ".md": "Markdown", ".mdx": "Markdown", ".json": "JSON", ".yml": "YAML", ".yaml": "YAML",
    ".css": "CSS", ".scss": "CSS", ".less": "CSS", ".html": "HTML",
    ".sh": "Shell", ".bash": "Shell", ".sql": "SQL", ".toml": "TOML", ".xml": "XML",
}


class GithubClientError(Exception):
    """Base for all errors with a friendly, user-safe message attached."""

    def __init__(self, friendly_message: str) -> None:
        self.friendly_message = friendly_message
        super().__init__(friendly_message)


class InvalidRepoUrlError(GithubClientError):
    pass


class RepoNotFoundError(GithubClientError):
    pass


class RepoPrivateError(GithubClientError):
    pass


class RepoTooLargeError(GithubClientError):
    pass


class GithubRateLimitError(GithubClientError):
    pass


class GithubUnavailableError(GithubClientError):
    pass


def parse_github_url(url: str) -> tuple[str, str]:
    """Strictly validates a public github.com repo URL and returns (owner, repo).

    Accepts with/without a trailing `.git`, with/without a trailing slash,
    with/without `www.`. Rejects anything not on github.com (gitlab, bitbucket,
    github enterprise, raw.githubusercontent.com, etc.) and anything with extra
    path segments (e.g. a specific file or PR URL).
    """
    url = url.strip()
    match = GITHUB_URL_RE.match(url)
    if not match:
        raise InvalidRepoUrlError(
            "That doesn't look like a public GitHub repo URL. Try something like "
            "https://github.com/owner/repo."
        )
    return match.group("owner"), match.group("repo")


@dataclass(frozen=True)
class ExtractedFile:
    path: str
    content: str
    size_bytes: int
    language: str


@dataclass(frozen=True)
class ExtractedRepo:
    files: list[ExtractedFile]


def _auth_headers(settings: Settings) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def fetch_repo_metadata(owner: str, repo: str, settings: Settings) -> dict:
    """Single API call: confirms the repo exists, is public, and returns its
    default branch. Raises a friendly, classified error on any problem."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        async with httpx.AsyncClient(timeout=settings.github_request_timeout_seconds) as client:
            response = await client.get(url, headers=_auth_headers(settings))
    except httpx.TimeoutException as exc:
        raise GithubUnavailableError("GitHub took too long to respond. Try again in a moment.") from exc
    except httpx.RequestError as exc:
        raise GithubUnavailableError("Couldn't reach GitHub right now. Try again in a moment.") from exc

    if response.status_code == 404:
        raise RepoNotFoundError(
            "That repo doesn't exist, or it's private — Duck only works with public repos."
        )
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise GithubRateLimitError(
            "GitHub's rate limit was hit. Try again in a few minutes, or set GITHUB_TOKEN to raise the limit."
        )
    if response.status_code != 200:
        raise GithubUnavailableError("GitHub returned an unexpected error. Try again in a moment.")

    data = response.json()
    if data.get("private"):
        raise RepoPrivateError("Duck only works with public repos right now.")

    return data


async def download_tarball(owner: str, repo: str, ref: str, settings: Settings) -> bytes:
    """Single request: the whole repo as a gzipped tarball at `ref`."""
    url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{ref}"
    try:
        async with httpx.AsyncClient(
            timeout=settings.github_request_timeout_seconds, follow_redirects=True
        ) as client:
            response = await client.get(url, headers=_auth_headers(settings))
    except httpx.TimeoutException as exc:
        raise GithubUnavailableError("GitHub took too long to send the repo. Try again in a moment.") from exc
    except httpx.RequestError as exc:
        raise GithubUnavailableError("Couldn't reach GitHub right now. Try again in a moment.") from exc

    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise GithubRateLimitError(
            "GitHub's rate limit was hit. Try again in a few minutes, or set GITHUB_TOKEN to raise the limit."
        )
    if response.status_code == 404:
        raise RepoNotFoundError("That repo or branch couldn't be found.")
    if response.status_code != 200:
        raise GithubUnavailableError("GitHub returned an unexpected error while downloading the repo.")

    return response.content


def _should_skip_path(path_parts: tuple[str, ...]) -> bool:
    return any(part in _SKIP_DIRS for part in path_parts[:-1])


def _should_skip_file(filename: str) -> bool:
    if filename in _SKIP_FILENAMES:
        return True
    if filename.endswith(".min.js") or filename.endswith(".min.css"):
        return True
    lower = filename.lower()
    for ext in _SKIP_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


def _language_for(filename: str) -> str:
    for ext, lang in _LANGUAGE_BY_EXTENSION.items():
        if filename.lower().endswith(ext):
            return lang
    return "Text"


def _looks_binary(raw: bytes) -> bool:
    return b"\x00" in raw[:1024]


def extract_text_files(tarball_bytes: bytes, settings: Settings) -> ExtractedRepo:
    """Extracts filtered text files from a GitHub tarball (which always has a
    single top-level `<owner>-<repo>-<sha>/` directory that gets stripped).

    Raises RepoTooLargeError (without storing anything) if the repo exceeds the
    configured file-count or total-byte caps.
    """
    files: list[ExtractedFile] = []
    total_bytes = 0

    with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue

            # Strip the top-level "<owner>-<repo>-<sha>/" directory GitHub always adds.
            parts = member.name.split("/")[1:]
            if not parts:
                continue
            path = "/".join(parts)
            filename = parts[-1]

            if _should_skip_path(tuple(parts)):
                continue
            if _should_skip_file(filename):
                continue
            if member.size > settings.repo_max_file_bytes:
                continue

            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            raw = extracted.read()

            if _looks_binary(raw):
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue

            files.append(ExtractedFile(path=path, content=content, size_bytes=len(raw), language=_language_for(filename)))
            total_bytes += len(raw)

            if len(files) > settings.repo_max_files or total_bytes > settings.repo_max_total_bytes:
                raise RepoTooLargeError(
                    "Duck works best on small to medium repos. This one has too many files "
                    "(or too much text) to connect right now."
                )

    return ExtractedRepo(files=files)
