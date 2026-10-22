"""Real network test against the live taskboard sample repo on GitHub. Skipped
by default — set RUN_GITHUB_INTEGRATION_TESTS=1 to enable once taskboard has
been pushed (see docs/sample_bugs.md in the duck repo for the push commands).
"""
import os

import pytest

from app.config import Settings
from app.services.github_client import download_tarball, extract_text_files, fetch_repo_metadata

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_GITHUB_INTEGRATION_TESTS") != "1",
    reason="set RUN_GITHUB_INTEGRATION_TESTS=1 to run (needs network + a pushed taskboard repo)",
)


@pytest.mark.asyncio
async def test_connect_real_taskboard_repo() -> None:
    settings = Settings()
    owner = os.environ.get("TASKBOARD_GITHUB_OWNER", "")
    assert owner, "set TASKBOARD_GITHUB_OWNER to your GitHub username to run this test"

    metadata = await fetch_repo_metadata(owner, "taskboard", settings)
    tarball = await download_tarball(owner, "taskboard", metadata["default_branch"], settings)
    extracted = extract_text_files(tarball, settings)

    assert len(extracted.files) > 0
    assert any(f.path.endswith("package.json") for f in extracted.files)
