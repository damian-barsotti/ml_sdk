from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel
from ml_sdk.api.users import Users, User

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

users = Users()


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class Auth:

    oauth2_scheme = None

    def __init__(self):

        self._validate_instance()

        self.router = APIRouter()

    def _validate_instance(self):
        assert self.oauth2_scheme is not None, ("You have to setup a"
                                                " oauth2_scheme")

    def create_access_token(
            self, data: dict,
            expires_delta: timedelta | None = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def get_current_user(self):

        async def _inner(token: Annotated[str, Depends(self.oauth2_scheme)]):

            credentials_exception = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                username: str = payload.get("sub")
                if username is None:
                    raise credentials_exception
                token_data = TokenData(username=username)
            except InvalidTokenError:
                raise credentials_exception
            user = users.get(username=token_data.username)
            if user is None:
                raise credentials_exception
            return user

        return _inner

    async def get_current_active_user(self):

        async def _inner(current_user: Annotated[
                User, Depends(self.get_current_user())]):

            if current_user.disabled:
                raise HTTPException(status_code=400, detail="Inactive user")
            return current_user

        return _inner

    def _add_routes(self):

        self.router.add_api_route("/token",
                                  self.login_for_access_token,
                                  methods=["POST"],
                                  response_model=Token)
        # self.router.add_api_route("/users/me/",
        #                           self.read_users_me,
        #                           methods=["GET"],
        #                           response_model=User)
        # self.router.add_api_route("/users/me/items/",
        #                           self.read_own_items,
        #                           methods=["GET"])

    async def login_for_access_token(
        self,
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    ) -> Token:
        user = users.authenticate(form_data.username,
                                  form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return Token(access_token=access_token, token_type="bearer")

    # async def read_users_me(
    #     self,
    #     current_user: Annotated[User, Depends(get_current_active_user)],
    # ):
    #     return current_user

    # async def read_own_items(
    #     self,
    #     current_user: Annotated[User, Depends(get_current_active_user)],
    # ):
    #     return [{"item_id": "Foo", "owner": current_user.username}]
