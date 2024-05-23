from typing import List, Dict
from ml_sdk.io.input import (
    TextInput,
    InferenceInput,
)
from ml_sdk.io.version import ModelVersion, ModelDescription, AvailableModels
from ml_sdk.io.output import (
    Output,
    ClassificationOutput,
    InferenceOutput,
    ScoreOutput
)


JobID = str


class Job(Output):
    job_id: JobID
    total: int
    processed: int = 0
    started_at: str = None
    end_at: str = None


class TestJob(Job):
    results: List[Dict] = []


class TrainJob(Job):
    version: ModelVersion = None


__all__ = [
    'TextInput',
    'InferenceInput',
    'InferenceOutput',
    'ClassificationOutput',
    'ScoreOutput',
    'MultiClassificationOutput',
    'ModelVersion',
    'ModelDescription',
    'AvailableModels',
    'TrainJob',
    'TestJob',
]
