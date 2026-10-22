from pydantic import BaseModel


class RepoOut(BaseModel):
    id: str
    github_url: str
    owner: str
    name: str
    default_branch: str
