from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": (
            "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"),
        "disabled": False,
    }
}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


class Auth:

    def __init__(self, base_dname, router):

        self.router = router

        self._add_routes()

        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        self.oauth2_scheme = OAuth2PasswordBearer(
            tokenUrl=f"{base_dname}/token")

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return self.pwd_context.hash(password)

    def get_user(self, db, username: str):
        if username in db:
            user_dict = db[username]
            return UserInDB(**user_dict)

    def authenticate_user(self, fake_db, username: str, password: str):
        user = self.get_user(fake_db, username)
        if not user:
            return False
        if not self.verify_password(password, user.hashed_password):
            return False
        return user

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
            user = self.get_user(fake_users_db, username=token_data.username)
            if user is None:
                raise credentials_exception
            return user

        return _inner

    async def get_current_active_user(self):

        async def _inner(
                current_user: Annotated[
                    User, Depends(self.get_current_user())],):

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
        user = self.authenticate_user(fake_users_db,
                                      form_data.username,
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
