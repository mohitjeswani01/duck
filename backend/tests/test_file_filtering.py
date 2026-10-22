import io
import tarfile

import pytest

from app.config import Settings
from app.services.github_client import RepoTooLargeError, extract_text_files


def _make_tarball(files: dict[str, bytes], top_dir: str = "owner-repo-abc123") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path, content in files.items():
            info = tarfile.TarInfo(name=f"{top_dir}/{path}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _settings(**overrides) -> Settings:
    defaults = dict(repo_max_files=500, repo_max_file_bytes=200_000, repo_max_total_bytes=5_000_000)
    defaults.update(overrides)
    return Settings(**defaults)


def test_keeps_normal_text_files() -> None:
    tarball = _make_tarball({"src/index.js": b"console.log('hi');\n", "README.md": b"# Hello\n"})
    result = extract_text_files(tarball, _settings())
    paths = {f.path for f in result.files}
    assert paths == {"src/index.js", "README.md"}


@pytest.mark.parametrize(
    "path",
    [
        "node_modules/pkg/index.js",
        "dist/bundle.js",
        "build/out.js",
        ".next/static/chunk.js",
        ".git/config",
        "vendor/lib.php",
    ],
)
def test_skips_ignored_directories(path: str) -> None:
    tarball = _make_tarball({path: b"ignored content", "keep.js": b"kept"})
    result = extract_text_files(tarball, _settings())
    paths = {f.path for f in result.files}
    assert path not in paths
    assert "keep.js" in paths


@pytest.mark.parametrize(
    "filename",
    ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock", "app.min.js", "styles.min.css", "logo.png"],
)
def test_skips_ignored_files(filename: str) -> None:
    tarball = _make_tarball({filename: b"ignored", "keep.ts": b"kept"})
    result = extract_text_files(tarball, _settings())
    paths = {f.path for f in result.files}
    assert filename not in paths
    assert "keep.ts" in paths


def test_skips_binary_files() -> None:
    tarball = _make_tarball({"data.bin": b"\x00\x01\x02binary", "keep.py": b"print('hi')"})
    result = extract_text_files(tarball, _settings())
    paths = {f.path for f in result.files}
    assert "data.bin" not in paths
    assert "keep.py" in paths


def test_skips_oversized_single_file() -> None:
    tarball = _make_tarball({"huge.txt": b"x" * 1000, "small.txt": b"y" * 10})
    result = extract_text_files(tarball, _settings(repo_max_file_bytes=100))
    paths = {f.path for f in result.files}
    assert "huge.txt" not in paths
    assert "small.txt" in paths


def test_rejects_repo_over_file_count_cap() -> None:
    files = {f"file_{i}.txt": b"content" for i in range(10)}
    tarball = _make_tarball(files)
    with pytest.raises(RepoTooLargeError):
        extract_text_files(tarball, _settings(repo_max_files=3))


def test_rejects_repo_over_total_byte_cap() -> None:
    files = {f"file_{i}.txt": b"x" * 1000 for i in range(10)}
    tarball = _make_tarball(files)
    with pytest.raises(RepoTooLargeError):
        extract_text_files(tarball, _settings(repo_max_files=500, repo_max_total_bytes=2000))


def test_language_detection() -> None:
    tarball = _make_tarball({"main.py": b"x", "app.ts": b"x", "notes.md": b"x", "unknown.xyz": b"x"})
    result = extract_text_files(tarball, _settings())
    by_path = {f.path: f.language for f in result.files}
    assert by_path["main.py"] == "Python"
    assert by_path["app.ts"] == "TypeScript"
    assert by_path["notes.md"] == "Markdown"
    assert by_path["unknown.xyz"] == "Text"
