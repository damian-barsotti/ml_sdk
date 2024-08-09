import logging
import traceback
from fastapi import (status,
                     UploadFile, BackgroundTasks,
                     HTTPException, Depends)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Annotated
from ml_sdk.api.parsers import CSVFileParser
from ml_sdk.communication.redis import RedisDispatcher, RedisSettings
from ml_sdk.database.redis import RedisDatabase
from ml_sdk.database.mongo import MongoDatabase, MongoSettings
from ml_sdk.io import (
    TestJob,
    TrainJob,
    JobID,
)
from ml_sdk.io.version import (ModelVersion, ModelDescription,
                               VersionID, AvailableModels)

from ml_sdk.api.auth import Auth

logger = logging.getLogger()

ImageInput = UploadFile
FileInput = UploadFile


class MLAPI(Auth):
    MODEL_NAME = None
    DESCRIPTION = None
    INPUT_TYPE = None
    OUTPUT_TYPE = None
    COMMUNICATION_TYPE = RedisDispatcher
    DATABASE_TYPE = RedisDatabase
    FILE_PARSER = CSVFileParser
    BATCH_SIZE = 1000

    def __init__(self):

        self._validate_instance()

        super().__init__()

        # Communication
        if self.COMMUNICATION_TYPE == RedisDispatcher:
            comm_settings = RedisSettings(topic=self.MODEL_NAME, host='redis')
        else:
            raise NotImplementedError("Communication type not implemented")
        self.connector = self.COMMUNICATION_TYPE(comm_settings)

        # Database
        if self.DATABASE_TYPE == RedisDatabase:
            db_settings = RedisSettings(topic=f"{self.MODEL_NAME}_jobs",
                                        host='redis')
        elif self.DATABASE_TYPE == MongoDatabase:
            db_settings = MongoSettings(db=self.MODEL_NAME, host='mongo')
        else:
            raise NotImplementedError("Database type not implemented")
        self.database = self.DATABASE_TYPE(db_settings)

        # API Routes
        self._add_routes()
        super()._add_routes()

    def _validate_instance(self):
        assert self.INPUT_TYPE is not None, "You have to setup an INPUT_TYPE"
        assert self.OUTPUT_TYPE is not None, "You have to setup an OUTPUT_TYPE"
        assert self.COMMUNICATION_TYPE is not None, ("You have to setup"
                                                     " a COMMUNICATION_TYPE")
        assert self.DATABASE_TYPE is not None, ("You have to setup"
                                                " a DATABASE_TYPE")
        assert self.MODEL_NAME is not None, "You have to setup a MODEL_NAME"
        assert callable(
            self.FILE_PARSER), "You have to setup first a FILE_PARSER"
        assert self.oauth2_scheme is not None, ("You have to setup"
                                                " a oauth2_scheme")

    def _add_routes(self):
        self.router.add_api_route("/",
                                  self.index,
                                  methods=["GET"],
                                  response_model=ModelDescription)
        self.router.add_api_route("/predict",
                                  self.post_predict(),
                                  methods=["POST"],
                                  response_model=self.OUTPUT_TYPE)
        self.router.add_api_route("/test",
                                  self.post_test(),
                                  methods=["POST"],
                                  response_model=TestJob)
        self.router.add_api_route("/test/{job_id}",
                                  self.get_test,
                                  methods=["GET"],
                                  response_model=TestJob)
        self.router.add_api_route("/train",
                                  self.post_train,
                                  methods=["POST"],
                                  response_model=TrainJob)
        self.router.add_api_route("/train/{job_id}",
                                  self.get_train,
                                  methods=["GET"],
                                  response_model=TrainJob)
        self.router.add_api_route("/version/{version_id}",
                                  self.post_version(),
                                  methods=["POST"],
                                  response_model=ModelVersion)
        self.router.add_api_route("/version",
                                  self.get_version(),
                                  methods=["GET"])

    # VIEWS
    def post_predict(self):

        def _inner(token: Annotated[str, Depends(self.oauth2_scheme)],
                   input_: self.INPUT_TYPE) -> self.OUTPUT_TYPE:
            try:
                result = self.connector.dispatch('predict',
                                                 input_=input_.dict())
            except ValueError:
                raise HTTPException(
                    status_code=404, detail="Service timeout for predict")
            return result

        return _inner

    def get_test(self, job_id: JobID, as_file: bool = False) -> TestJob:
        # Job results
        job = self.database.get_test_job(JobID(job_id))

        # Return file or formatted response
        if as_file:
            job.results = [self.OUTPUT_TYPE(**res) for res in job.results]
            return self._create_file(job)
        else:
            job.results = [self.OUTPUT_TYPE(**res) for res in job.results[:10]]
            return job

    def post_test(self):

        def _inner(token: Annotated[str, Depends(self.oauth2_scheme)],
                   input_: FileInput,
                   background_tasks: BackgroundTasks) -> TestJob:
            # parsing
            items = list(self._parse_file(input_))  # TODO consume 1 by 1

            # job creation
            job = self.database.create_test_job(total=len(items))

            # trigger tasks
            self._async_predict(token, background_tasks, job=job, items=items)

            return job

        return _inner

    def get_train(self, job_id: JobID) -> TrainJob:
        return self.database.get_train_job(JobID(job_id))

    def post_train(self,
                   background_tasks: BackgroundTasks,
                   input_: FileInput) -> TrainJob:
        # parsing
        items = list(self._parse_file(input_))  # TODO consume 1 by 1
        # TODO move this parsing to the async_train
        try:
            for i in items:
                i.update({
                    "input": {
                        k: i[k]
                        for k in self.INPUT_TYPE.__fields__
                    }
                })
            items = [self.OUTPUT_TYPE(**reg).dict() for reg in items]

        except Exception as exc:
            traceback.print_exc()
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=jsonable_encoder(
                    {"detail": exc, "Error": "Input file corrupt"}),
            )

        # job creation
        job = self.database.create_train_job()

        # trigger train task
        self._async_train(background_tasks, job=job, items=items)
        return job

    def get_version(self):

        def _inner(token: Annotated[str, Depends(self.oauth2_scheme)]
                   ) -> AvailableModels:

            try:
                result = self.connector.dispatch('available_versions')
            except ValueError:
                raise HTTPException(
                    status_code=404,
                    detail="Service timeout for available_versions")

            logger.info(f"get_version {result=}")
            return result

        return _inner

    def post_version(self):

        def _inner(token: Annotated[str, Depends(self.oauth2_scheme)],
                   version_id: VersionID) -> ModelVersion:
            input_ = ModelVersion(version=version_id)
            self.connector.broadcast('deploy', input_=input_.dict())
            return input_

        return _inner

    def index(self) -> ModelDescription:

        try:
            version = self.connector.dispatch('enabled_version')
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Service timeout for enabled_version")

        return ModelDescription(
            **{"model": self.MODEL_NAME,
               "description": self.DESCRIPTION,
               "version": version})

    # INTERNAL
    def _parse_file(self, input_: FileInput):
        parser = self.FILE_PARSER()
        items = parser.parse(input_.file)
        yield from items

    def _create_file(self, job: TestJob):
        filename = self.FILE_PARSER.generate_filename(prefix=self.MODEL_NAME)
        media_type = self.FILE_PARSER.mediatype
        lines = job.results
        with self.FILE_PARSER.build(lines=lines) as file_content:
            response = StreamingResponse(file_content,
                                         media_type=media_type)
            response.headers["Content-Disposition"] = (
                f"attachment; filename={filename}")
        return response

    def _async_predict(self, token, background_tasks: BackgroundTasks,
                       job: TestJob, items: List):
        def _inner(token, database, job, items):
            predict_func = self.post_predict()
            for item in items:
                try:
                    item = self.INPUT_TYPE(**item)
                except Exception as e:
                    logger.info(
                        f"Ommited {item} Failure during parsing: {str(e)}")
                else:
                    inference_result = predict_func(token, item)
                    self.database.update_test_job(
                        job=job, task=self.OUTPUT_TYPE(**inference_result))

        for i in range(0, len(items), self.BATCH_SIZE):
            background_tasks.add_task(_inner, token, self.database, job,
                                      items[i:i+self.BATCH_SIZE])

    def _async_train(self, background_tasks, job: TestJob, items: List):
        # TODO refactor this controlling threads with batch size

        def _inner(database, job, items):

            try:
                model_version = self.connector.dispatch('train', input_=items)
            except ValueError:
                raise HTTPException(
                    status_code=404,
                    detail="Service timeout for train")

            self.database.update_train_job(job=job, version=model_version)

        background_tasks.add_task(_inner, self.database, job, items)
