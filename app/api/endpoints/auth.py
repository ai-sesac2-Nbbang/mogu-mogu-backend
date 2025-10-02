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

        # 3. 기존 사용자 확인 또는 새 사용자 생성
        user = await session.scalar(
            select(User).where(User.kakao_id == kakao_user_info.id)
        )

        if user is None:
            # 새 사용자 생성
            # 카카오 계정에서 이메일 정보 추출
            kakao_account = kakao_user_info.kakao_account
            email = None
            if kakao_account.get("email"):
                email = kakao_account["email"]
            elif kakao_account.get("email_verified"):
                email = kakao_account.get("email")

            if not email:
                # 이메일이 없는 경우 앱으로 에러와 함께 리다이렉트
                settings = get_settings()
                error_params = urlencode(
                    {
                        "ok": "false",
                        "message": "카카오 계정에서 이메일 정보를 가져올 수 없습니다.",
                    }
                )
                error_url = f"{settings.security.app_deep_link}?{error_params}"
                return RedirectResponse(
                    url=error_url, status_code=status.HTTP_302_FOUND
                )

            # 카카오 프로필 정보 추출
            profile = kakao_account.get("profile", {})
            nickname = profile.get("nickname")
            profile_image_url = profile.get("profile_image_url")

            # 새 사용자 생성 (status=pending_onboarding)
            user = User(
                email=email,
                kakao_id=kakao_user_info.id,
                provider="kakao",
                nickname=nickname,
                profile_image_url=profile_image_url,
                status=UserStatusEnum.PENDING_ONBOARDING.value,
            )
            session.add(user)
            await session.commit()

        # 4. JWT 토큰 생성 (상태와 무관하게 항상 발급)
        jwt_token = create_jwt_token(user_id=user.id)

        # 5. 리프레시 토큰 생성
        refresh_token = RefreshToken(
            user_id=user.id,
            refresh_token=secrets.token_urlsafe(32),
            exp=int(time.time() + get_settings().security.refresh_token_expire_secs),
        )
        session.add(refresh_token)
        await session.commit()

        # 6. 사용자 상태에 따라 다른 응답
        settings = get_settings()

        # 온보딩이 필요한 경우
        if user.status == UserStatusEnum.PENDING_ONBOARDING.value:
            success_params = urlencode(
                {
                    "ok": "true",
                    "need_onboarding": "true",
                    "access_token": jwt_token.access_token,
                    "expires_at": str(jwt_token.payload.exp),
                    "refresh_token": refresh_token.refresh_token,
                    "refresh_token_expires_at": str(refresh_token.exp),
                }
            )
        else:
            # 이미 온보딩 완료된 사용자 - 일반 로그인
            success_params = urlencode(
                {
                    "ok": "true",
                    "need_onboarding": "false",
                    "access_token": jwt_token.access_token,
                    "expires_at": str(jwt_token.payload.exp),
                    "refresh_token": refresh_token.refresh_token,
                    "refresh_token_expires_at": str(refresh_token.exp),
                }
            )

        success_url = f"{settings.security.app_deep_link}?{success_params}"
        return RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)

    except HTTPException as e:
        # HTTP 예외를 앱으로 전달
        settings = get_settings()
        error_params = urlencode({"ok": "false", "message": str(e.detail)})
        error_url = f"{settings.security.app_deep_link}?{error_params}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        # 기타 예외를 앱으로 전달
        settings = get_settings()
        error_params = urlencode(
            {
                "ok": "false",
                "message": f"카카오 로그인 처리 중 오류가 발생했습니다: {str(e)}",
            }
        )
        error_url = f"{settings.security.app_deep_link}?{error_params}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)


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
    token = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.refresh_token == data.refresh_token)
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

    token.used = True
    session.add(token)

    jwt_token = create_jwt_token(user_id=token.user_id)

    refresh_token = RefreshToken(
        user_id=token.user_id,
        refresh_token=secrets.token_urlsafe(32),
        exp=int(time.time() + get_settings().security.refresh_token_expire_secs),
    )
    session.add(refresh_token)
    await session.commit()

    return AccessTokenResponse(
        access_token=jwt_token.access_token,
        expires_at=jwt_token.payload.exp,
        refresh_token=refresh_token.refresh_token,
        refresh_token_expires_at=refresh_token.exp,
    )
