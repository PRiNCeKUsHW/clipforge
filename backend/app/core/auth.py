"""Email/password auth with JWTs (fastapi-users).

Two ways to send the JWT:
  * cookie  (httpOnly "clipforge_auth"): used by the web app; works with EventSource/SSE.
  * bearer  (Authorization: Bearer ...): handy for scripts and the Swagger UI.
"""

import uuid
from collections.abc import AsyncIterator

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, InvalidPasswordException, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, CookieTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import User

settings = get_settings()


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    async def validate_password(self, password: str, user) -> None:  # type: ignore[override]
        if len(password) < 8:
            raise InvalidPasswordException(reason="Password must be at least 8 characters")
        if user.email and user.email.lower() in password.lower():
            raise InvalidPasswordException(reason="Password must not contain your email")


async def get_user_db(session: AsyncSession = Depends(get_session)) -> AsyncIterator[SQLAlchemyUserDatabase]:
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)) -> AsyncIterator[UserManager]:
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)


cookie_backend = AuthenticationBackend(
    name="cookie",
    transport=CookieTransport(
        cookie_name="clipforge_auth",
        cookie_max_age=settings.jwt_lifetime_seconds,
        cookie_secure=settings.cookie_secure,
        cookie_samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    ),
    get_strategy=get_jwt_strategy,
)

bearer_backend = AuthenticationBackend(
    name="jwt",
    transport=BearerTransport(tokenUrl="api/auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [cookie_backend, bearer_backend])

current_active_user = fastapi_users.current_user(active=True)
