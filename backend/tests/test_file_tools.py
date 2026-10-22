import asyncio

import pytest

from app.services import file_tools
from app.services.file_tools import (
    FileNotFoundInRepoError,
    InvalidSearchPatternError,
    PathTraversalError,
    StoredFile,
    list_files_pure,
    read_file_pure,
    search_code_pure,
)

FILES = [
    StoredFile(path="src/index.ts", content="line1\nline2\nline3\n", size_bytes=20, language="TypeScript"),
    StoredFile(path="src/utils/math.ts", content="export function add(a, b) {\n  return a + b;\n}\n", size_bytes=40, language="TypeScript"),
    StoredFile(path="README.md", content="# Title\nSome text\n", size_bytes=18, language="Markdown"),
]


# ---- list_files ----

def test_list_files_no_pattern_returns_all_sorted() -> None:
    result = list_files_pure(FILES, None, max_results=200)
    assert [f.path for f in result.files] == ["README.md", "src/index.ts", "src/utils/math.ts"]
    assert not result.truncated


def test_list_files_directory_prefix() -> None:
    result = list_files_pure(FILES, "src/utils", max_results=200)
    assert [f.path for f in result.files] == ["src/utils/math.ts"]


def test_list_files_glob_pattern() -> None:
    # fnmatch's "*" isn't directory-scoped, so this matches both .ts files under src/.
    result = list_files_pure(FILES, "src/*.ts", max_results=200)
    assert {f.path for f in result.files} == {"src/index.ts", "src/utils/math.ts"}

    result = list_files_pure(FILES, "*.md", max_results=200)
    assert {f.path for f in result.files} == {"README.md"}


def test_list_files_caps_results() -> None:
    many = [StoredFile(path=f"f{i}.txt", content="x", size_bytes=1, language="Text") for i in range(10)]
    result = list_files_pure(many, None, max_results=3)
    assert len(result.files) == 3
    assert result.total_matches == 10
    assert result.truncated


# ---- read_file ----

def test_read_file_full_short_file() -> None:
    result = read_file_pure(FILES, "src/index.ts", None, None, max_lines=300)
    assert result.total_lines == 3
    assert not result.truncated
    assert "1\tline1" in result.content
    assert "3\tline3" in result.content


def test_read_file_line_range() -> None:
    result = read_file_pure(FILES, "src/utils/math.ts", 2, 2, max_lines=300)
    assert result.start_line == 2
    assert result.end_line == 2
    assert "return a + b" in result.content
    assert "export function" not in result.content


def test_read_file_truncates_long_file() -> None:
    long_file = StoredFile(
        path="big.txt", content="\n".join(f"line{i}" for i in range(1000)), size_bytes=1, language="Text"
    )
    result = read_file_pure([long_file], "big.txt", None, None, max_lines=100)
    assert result.truncated
    assert result.total_lines == 1000
    assert result.end_line == 100
    assert "truncated" in result.content


def test_read_file_not_found_raises() -> None:
    with pytest.raises(FileNotFoundInRepoError):
        read_file_pure(FILES, "does/not/exist.ts", None, None, max_lines=300)


@pytest.mark.parametrize(
    "path",
    ["../etc/passwd", "/etc/passwd", "src/../../etc/passwd", "a/..", "..", "a//b"],
)
def test_read_file_rejects_path_traversal(path: str) -> None:
    with pytest.raises(PathTraversalError):
        read_file_pure(FILES, path, None, None, max_lines=300)


# ---- search_code ----

def test_search_code_literal_match() -> None:
    result = search_code_pure(FILES, "return a + b", None, is_regex=False, max_results=50)
    assert result.total_matches == 1
    assert result.matches[0].path == "src/utils/math.ts"
    assert result.matches[0].line_number == 2


def test_search_code_regex_match() -> None:
    result = search_code_pure(FILES, r"function \w+\(", None, is_regex=True, max_results=50)
    assert result.total_matches == 1
    assert result.matches[0].path == "src/utils/math.ts"


def test_search_code_file_pattern_restricts_scope() -> None:
    result = search_code_pure(FILES, "line", "README.md", is_regex=False, max_results=50)
    assert result.total_matches == 0  # README has no literal "line"


def test_search_code_invalid_regex_raises() -> None:
    with pytest.raises(InvalidSearchPatternError):
        search_code_pure(FILES, "(unclosed", None, is_regex=True, max_results=50)


def test_search_code_empty_query_raises() -> None:
    with pytest.raises(InvalidSearchPatternError):
        search_code_pure(FILES, "", None, is_regex=False, max_results=50)


def test_search_code_too_long_query_raises() -> None:
    with pytest.raises(InvalidSearchPatternError):
        search_code_pure(FILES, "x" * 500, None, is_regex=True, max_results=50)


def test_search_code_skips_overlong_lines_for_regex() -> None:
    long_line = "a" * 1000 + "NEEDLE"
    short_line = "NEEDLE here"
    f = StoredFile(path="f.txt", content=f"{long_line}\n{short_line}\n", size_bytes=1, language="Text")
    result = search_code_pure([f], "NEEDLE", None, is_regex=True, max_results=50)
    # Only the short line should match; the overlong line is skipped for regex safety.
    assert result.total_matches == 1
    assert result.matches[0].line_number == 2


def test_search_code_caps_results() -> None:
    f = StoredFile(path="f.txt", content="\n".join("match" for _ in range(20)), size_bytes=1, language="Text")
    result = search_code_pure([f], "match", None, is_regex=False, max_results=5)
    assert len(result.matches) == 5
    assert result.total_matches == 20
    assert result.truncated


# ---- async search timeout wrapper ----

def test_search_with_timeout_returns_promptly_on_slow_search(monkeypatch: pytest.MonkeyPatch) -> None:
    def _slow(files, query, file_pattern, is_regex, max_results):
        import time

        time.sleep(1)
        return search_code_pure(files, query, file_pattern, is_regex, max_results)

    monkeypatch.setattr(file_tools, "search_code_pure", _slow)

    async def run():
        return await file_tools._search_with_timeout(FILES, "line", None, False, 50, timeout_seconds=0.05)

    result = asyncio.run(run())
    assert result.timed_out
    assert result.matches == []
