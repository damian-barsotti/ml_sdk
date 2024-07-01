from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional, Callable


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


class Users():

    fake_users_db = {
        "johndoe": {
            "username": "johndoe",
            "full_name": "John Doe",
            "email": "johndoe@example.com",
            "hashed_password": (
                "$2b$12$EixZaYVK1fsbw1ZfbX3OXe"
                "PaWxn96p36WQoeG6Lruj3vjPGga31lW"),
            "disabled": False,
        }
    }

    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
