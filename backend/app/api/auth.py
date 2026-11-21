from fastapi import APIRouter

from app.core.auth import bearer_backend, cookie_backend, fastapi_users
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter()

# POST /api/auth/cookie/login (form: username, password) -> sets httpOnly cookie; /logout clears it
router.include_router(fastapi_users.get_auth_router(cookie_backend), prefix="/auth/cookie", tags=["auth"])
# POST /api/auth/jwt/login -> {"access_token": ...} for Authorization: Bearer
router.include_router(fastapi_users.get_auth_router(bearer_backend), prefix="/auth/jwt", tags=["auth"])
# POST /api/auth/register
router.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
# GET/PATCH /api/users/me
router.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])
