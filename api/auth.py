from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable
import jwt
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel
import yaml
from ml_sdk.api.users import Users, User, UserInDB

CONF_FILE = "/app/users/conf.yml"

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

        with open(CONF_FILE, 'r') as file:
            self.conf = yaml.safe_load(file)

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
        encoded_jwt = jwt.encode(
            to_encode, self.conf['SECRET_KEY'],
            algorithm=self.conf['ALGORITHM'])
        return encoded_jwt

    async def get_current_user(self):

        async def _inner(token: Annotated[str, Depends(self.oauth2_scheme)]):

            credentials_exception = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

            try:
                payload = jwt.decode(token, self.conf['SECRET_KEY'],
                                     algorithm=self.conf['ALGORITHM'])
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
        authenticator:
        Callable[[str, str], UserInDB] = Depends(users.authenticator)
    ) -> Token:
        user = authenticator(form_data.username,
                             form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(
            minutes=self.conf['ACCESS_TOKEN_EXPIRE_MINUTES'])
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
