import pytest

from app.services.github_client import InvalidRepoUrlError, parse_github_url


@pytest.mark.parametrize(
    "url,expected_owner,expected_repo",
    [
        ("https://github.com/owner/repo", "owner", "repo"),
        ("https://github.com/owner/repo.git", "owner", "repo"),
        ("https://github.com/owner/repo/", "owner", "repo"),
        ("https://github.com/owner/repo.git/", "owner", "repo"),
        ("http://github.com/owner/repo", "owner", "repo"),
        ("https://www.github.com/owner/repo", "owner", "repo"),
        ("https://github.com/the-owner/the-repo_name.js", "the-owner", "the-repo_name.js"),
        ("  https://github.com/owner/repo  ", "owner", "repo"),
    ],
)
def test_parse_valid_urls(url: str, expected_owner: str, expected_repo: str) -> None:
    owner, repo = parse_github_url(url)
    assert owner == expected_owner
    assert repo == expected_repo


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "https://gitlab.com/owner/repo",
        "https://github.com/owner",
        "https://github.com/owner/repo/extra",
        "https://github.com/owner/repo/pull/1",
        "ftp://github.com/owner/repo",
        "https://raw.githubusercontent.com/owner/repo/main/file.py",
        "https://github.com/",
        "",
        "https://github.com//repo",
    ],
)
def test_parse_invalid_urls_raise(url: str) -> None:
    with pytest.raises(InvalidRepoUrlError):
        parse_github_url(url)
