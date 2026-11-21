"""Connected accounts (YouTube, Instagram) via OAuth."""

import logging
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_active_user
from app.core.config import get_settings
from app.core.crypto import TokenCipher
from app.core.db import get_session
from app.models import Platform, SocialAccount, User
from app.schemas.clip import SocialAccountRead
from app.services import oauth

log = logging.getLogger(__name__)
router = APIRouter(tags=["accounts"])

PLATFORMS = {"youtube": Platform.youtube, "instagram": Platform.instagram}


def _platform(name: str) -> Platform:
    if name not in PLATFORMS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown platform")
    return PLATFORMS[name]


def _cipher() -> TokenCipher:
    try:
        return TokenCipher(get_settings().token_encryption_key)
    except ValueError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/oauth/providers")
async def providers() -> dict[str, bool]:
    """Which platforms have OAuth credentials configured (the UI hides the others)."""
    return oauth.configured(get_settings())


@router.get("/oauth/{platform}/start")
async def oauth_start(platform: str, user: User = Depends(current_active_user)) -> RedirectResponse:
    settings = get_settings()
    _platform(platform)
    if not oauth.configured(settings)[platform]:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"{platform} publishing isn't configured on this server")
    _cipher()  # fail early if tokens couldn't be stored
    state = oauth.make_state(settings.jwt_secret, user.id, platform)
    return RedirectResponse(oauth.authorize_url(settings, platform, state), status_code=status.HTTP_302_FOUND)


@router.get("/oauth/{platform}/callback")
async def oauth_callback(
    platform: str,
    session: AsyncSession = Depends(get_session),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """Google/Meta redirect the browser here. The signed `state` tells us which user is connecting."""
    settings = get_settings()
    back = f"{settings.frontend_url.rstrip('/')}/accounts"

    def done(**params: str) -> RedirectResponse:
        return RedirectResponse(f"{back}?{urlencode(params)}", status_code=status.HTTP_302_FOUND)

    plat = _platform(platform)
    if error:
        return done(error=error_description or error)
    if not code or not state:
        return done(error="Missing authorization code")
    try:
        user_id = oauth.read_state(settings.jwt_secret, state, platform)
        async with httpx.AsyncClient(timeout=30) as http:
            if plat == Platform.youtube:
                acct = await oauth.connect_youtube(settings, code, http)
            else:
                acct = await oauth.connect_instagram(settings, code, http)
    except oauth.OAuthError as exc:
        return done(error=str(exc))
    except httpx.HTTPError as exc:
        log.exception("OAuth network error")
        return done(error=f"Couldn't reach {platform}: {exc}")

    cipher = _cipher()
    existing = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == plat,
                SocialAccount.external_account_id == acct.external_id,
            )
        )
    ).scalar_one_or_none()
    row = existing or SocialAccount(user_id=user_id, platform=plat, external_account_id=acct.external_id)
    row.display_name = acct.display_name
    row.access_token_encrypted = cipher.encrypt(acct.access_token)
    if acct.refresh_token:  # Google only returns it on first consent; keep the old one otherwise
        row.refresh_token_encrypted = cipher.encrypt(acct.refresh_token)
    row.expires_at = acct.expires_at
    row.scopes = acct.scopes
    session.add(row)
    await session.commit()
    return done(connected=platform)


@router.get("/accounts", response_model=list[SocialAccountRead])
async def list_accounts(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
) -> list[SocialAccount]:
    rows = await session.execute(
        select(SocialAccount).where(SocialAccount.user_id == user.id).order_by(SocialAccount.created_at)
    )
    return list(rows.scalars().all())


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    account_id: uuid.UUID, user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
) -> Response:
    account = await session.get(SocialAccount, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    await session.delete(account)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
