from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Repo
from app.schemas.repo import RepoOut

router = APIRouter(prefix="/repos", tags=["repos"])


@router.get("", response_model=list[RepoOut])
async def list_repos(db: AsyncSession = Depends(get_db)) -> list[RepoOut]:
    """Lists connected repos. Empty until Phase 2 adds the GitHub connect flow."""
    result = await db.execute(select(Repo))
    repos = result.scalars().all()
    return [
        RepoOut(
            id=str(repo.id),
            github_url=repo.github_url,
            owner=repo.owner,
            name=repo.name,
            default_branch=repo.default_branch,
        )
        for repo in repos
    ]
