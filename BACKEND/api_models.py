from pydantic import BaseModel, Field


class AddToGithubPayload(BaseModel):
    name: str
    description: str = ""
    visibility: str = "public"


class InstallPayload(BaseModel):
    repos: list[str] = Field(default_factory=list)


class DeletePayload(BaseModel):
    repos: list[str] = Field(default_factory=list)


class RenamePayload(BaseModel):
    old_name: str
    new_name: str


class DeleteGithubPayload(BaseModel):
    name: str


class UpdateDescriptionPayload(BaseModel):
    name: str
    description: str = ""


class OpenFolderPayload(BaseModel):
    path: str


class PushPayload(BaseModel):
    path: str
    message: str = ""
    version_mode: str = "use_existing"
