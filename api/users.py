from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional, Callable
import yaml

USERS_FILE = "/app/users/users.yml"


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


class Users():

    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        with open(USERS_FILE, 'r') as file:
            self.fake_users_db = yaml.safe_load(file)

    def authenticator(self) -> Callable[[str, str], Optional[UserInDB]]:
        return self._authenticate

    def _authenticate(self, username: str, password: str
                      ) -> Optional[UserInDB]:
        user = self.get(username)
        if not user:
            return False
        if not self.verify_password(password, user.hashed_password):
            return False
        return user

    def get(self, username: str) -> UserInDB:
        if username in self.fake_users_db:
            user_dict = self.fake_users_db[username]
            return UserInDB(**user_dict)

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return self.pwd_context.hash(password)
