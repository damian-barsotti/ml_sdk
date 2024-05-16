from typing import Optional, List
from pydantic import BaseModel


VersionID = str


class Scores(BaseModel):
    precision: float
    recall: float


class ModelVersion(BaseModel):
    version: Optional[VersionID]
    scores: Optional[Scores]


class ModelDescription(BaseModel):
    model: str
    description: Optional[str]
    version: ModelVersion = None


class AvailableModels(BaseModel):
    enabled: ModelVersion
    availables: List[ModelVersion]
