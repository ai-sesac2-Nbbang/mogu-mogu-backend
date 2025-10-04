import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_messages, deps
from app.core.config import get_settings
from app.core.security.jwt import create_jwt_token
from app.core.security.kakao import (
    exchange_code_for_token,
    get_kakao_login_url,
    get_kakao_user_info,
)
from app.enums import UserStatusEnum
from app.models import RefreshToken, User
from app.schemas.requests import RefreshTokenRequest
from app.schemas.responses import AccessTokenResponse

router = APIRouter()
logger = logging.getLogger(__name__)


# 공통 헬퍼 함수들
async def _get_user_by_kakao_id(
    kakao_id: int,
    session: AsyncSession,
) -> User | None:
    """카카오 ID로 사용자를 조회합니다."""
    result = await session.scalar(select(User).where(User.kakao_id == kakao_id))
    return result


def _extract_kakao_user_info(
    kakao_user_info: Any,
) -> tuple[str | None, str | None, str | None]:
    """카카오 사용자 정보에서 이메일, 닉네임, 프로필 이미지를 추출합니다."""
    kakao_account = kakao_user_info.kakao_account

    # 이메일 추출
    email = None
    if kakao_account.get("email"):
        email = kakao_account["email"]
    elif kakao_account.get("email_verified"):
        email = kakao_account.get("email")

    # 프로필 정보 추출
    profile = kakao_account.get("profile", {})
    nickname = profile.get("nickname")
    profile_image_url = profile.get("profile_image_url")

    return email, nickname, profile_image_url


async def _create_new_user(
    email: str,
    kakao_id: int,
    nickname: str | None,
    profile_image_url: str | None,
    session: AsyncSession,
) -> User:
    """새 사용자를 생성합니다."""
    user = User(
        email=email,
        kakao_id=kakao_id,
        provider="kakao",
        nickname=nickname,
        profile_image_url=profile_image_url,
        status=UserStatusEnum.PENDING_ONBOARDING.value,
    )
    session.add(user)
    await session.commit()
    return user


async def _create_refresh_token(user_id: str, session: AsyncSession) -> RefreshToken:
    """새 리프레시 토큰을 생성합니다."""
    refresh_token = RefreshToken(
        user_id=user_id,
        refresh_token=secrets.token_urlsafe(32),
        exp=int(time.time() + get_settings().security.refresh_token_expire_secs),
    )
    session.add(refresh_token)
    return refresh_token


def _build_redirect_url(params: dict[str, str]) -> str:
    """리다이렉트 URL을 생성합니다."""
    settings = get_settings()
    encoded_params = urlencode(params)
    return f"{settings.security.app_deep_link}?{encoded_params}"


def _create_error_redirect(message: str) -> RedirectResponse:
    """에러 리다이렉트 응답을 생성합니다."""
    error_params = {"ok": "false", "message": message}
    error_url = _build_redirect_url(error_params)
    return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)


def _create_success_redirect(
    jwt_token: Any,
    refresh_token: RefreshToken,
    need_onboarding: bool,
) -> RedirectResponse:
    """성공 리다이렉트 응답을 생성합니다."""
    success_params = {
        "ok": "true",
        "need_onboarding": "true" if need_onboarding else "false",
        "access_token": jwt_token.access_token,
        "expires_at": str(jwt_token.payload.exp),
        "refresh_token": refresh_token.refresh_token,
        "refresh_token_expires_at": str(refresh_token.exp),
    }
    success_url = _build_redirect_url(success_params)
    return RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)


REFRESH_TOKEN_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "description": "Refresh token expired or is already used",
        "content": {
            "application/json": {
                "examples": {
                    "refresh token expired": {
                        "summary": api_messages.REFRESH_TOKEN_EXPIRED,
                        "value": {"detail": api_messages.REFRESH_TOKEN_EXPIRED},
                    },
                    "refresh token already used": {
                        "summary": api_messages.REFRESH_TOKEN_ALREADY_USED,
                        "value": {"detail": api_messages.REFRESH_TOKEN_ALREADY_USED},
                    },
                }
            }
        },
    },
    404: {
        "description": "Refresh token does not exist",
        "content": {
            "application/json": {
                "example": {"detail": api_messages.REFRESH_TOKEN_NOT_FOUND}
            }
        },
    },
}


@router.get(
    "/kakao/login",
    description="카카오 로그인 URL로 리다이렉트",
)
async def kakao_login_redirect() -> RedirectResponse:
    """카카오 로그인 페이지로 리다이렉트"""
    kakao_login_url = get_kakao_login_url()
    return RedirectResponse(url=kakao_login_url)


@router.get(
    "/kakao/callback",
    description="카카오 로그인 콜백 처리 및 앱으로 리다이렉트",
)
async def kakao_callback(
    code: str,
    session: AsyncSession = Depends(deps.get_session),
) -> RedirectResponse:
    """카카오 로그인 콜백 처리 후 앱으로 토큰과 함께 리다이렉트"""
    try:
        # 1. 카카오 인증 코드를 액세스 토큰으로 교환
        kakao_token = await exchange_code_for_token(code)

        # 2. 카카오 사용자 정보 조회
        kakao_user_info = await get_kakao_user_info(kakao_token.access_token)

        # 3. 기존 사용자 확인
        user = await _get_user_by_kakao_id(kakao_user_info.id, session)

        if user is None:
            # 4. 새 사용자 생성
            email, nickname, profile_image_url = _extract_kakao_user_info(
                kakao_user_info
            )

            if not email:
                logger.warning("카카오 계정에서 이메일 정보를 가져올 수 없음")
                return _create_error_redirect(
                    "카카오 계정에서 이메일 정보를 가져올 수 없습니다."
                )

            user = await _create_new_user(
                email, kakao_user_info.id, nickname, profile_image_url, session
            )

        # 5. JWT 토큰 생성
        jwt_token = create_jwt_token(user_id=user.id)

        # 6. 리프레시 토큰 생성
        refresh_token = await _create_refresh_token(user.id, session)
        await session.commit()

        # 7. 성공 리다이렉트
        need_onboarding = user.status == UserStatusEnum.PENDING_ONBOARDING.value
        logger.info(
            f"🔗 카카오 로그인 성공: user_id={user.id}, need_onboarding={need_onboarding}"
        )
        return _create_success_redirect(jwt_token, refresh_token, need_onboarding)

    except HTTPException as e:
        logger.warning(f"⚠️ 카카오 로그인 HTTP 에러: {e.detail}")
        return _create_error_redirect(str(e.detail))
    except Exception as e:
        logger.error(f"❌ 카카오 로그인 처리 중 오류: {str(e)}", exc_info=True)
        return _create_error_redirect(
            f"카카오 로그인 처리 중 오류가 발생했습니다: {str(e)}"
        )


async def _get_refresh_token(token_value: str, session: AsyncSession) -> RefreshToken:
    """리프레시 토큰을 조회하고 유효성을 검증합니다."""
    token = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.refresh_token == token_value)
        .with_for_update(skip_locked=True)
    )

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_messages.REFRESH_TOKEN_NOT_FOUND,
        )
    elif time.time() > token.exp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.REFRESH_TOKEN_EXPIRED,
        )
    elif token.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.REFRESH_TOKEN_ALREADY_USED,
        )

    return token


async def _revoke_and_create_new_tokens(
    old_token: RefreshToken, session: AsyncSession
) -> tuple[Any, RefreshToken]:
    """기존 토큰을 무효화하고 새로운 토큰들을 생성합니다."""
    # 기존 토큰 무효화
    old_token.used = True
    session.add(old_token)

    # 새 JWT 토큰 생성
    jwt_token = create_jwt_token(user_id=old_token.user_id)

    # 새 리프레시 토큰 생성
    new_refresh_token = await _create_refresh_token(old_token.user_id, session)

    return jwt_token, new_refresh_token


@router.post(
    "/refresh-token",
    response_model=AccessTokenResponse,
    responses=REFRESH_TOKEN_RESPONSES,
    description="OAuth2 compatible token, get an access token for future requests using refresh token",
)
async def refresh_token(
    data: RefreshTokenRequest,
    session: AsyncSession = Depends(deps.get_session),
) -> AccessTokenResponse:
    """리프레시 토큰으로 새로운 액세스 토큰을 발급받습니다."""
    # 리프레시 토큰 검증
    token = await _get_refresh_token(data.refresh_token, session)

    # 새 토큰 생성
    jwt_token, new_refresh_token = await _revoke_and_create_new_tokens(token, session)
    await session.commit()

    return AccessTokenResponse(
        access_token=jwt_token.access_token,
        expires_at=jwt_token.payload.exp,
        refresh_token=new_refresh_token.refresh_token,
        refresh_token_expires_at=new_refresh_token.exp,
    )
