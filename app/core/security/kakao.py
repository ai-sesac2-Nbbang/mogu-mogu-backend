from typing import Any

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings


class KakaoTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    refresh_token: str | None = None
    expires_in: int
    scope: str | None = None


class KakaoUserInfo(BaseModel):
    id: int
    connected_at: str
    properties: dict[str, Any]
    kakao_account: dict[str, Any]


async def exchange_code_for_token(authorization_code: str) -> KakaoTokenResponse:
    """카카오 인증 코드를 액세스 토큰으로 교환합니다."""
    settings = get_settings()

    data = {
        "grant_type": "authorization_code",
        "client_id": settings.kakao.rest_api_key.get_secret_value(),
        "client_secret": settings.kakao.client_secret.get_secret_value(),
        "redirect_uri": settings.kakao.redirect_uri,
        "code": authorization_code,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                settings.kakao.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            response.raise_for_status()

            token_data = response.json()

            # 카카오 API 응답에서 필요한 필드 추출
            return KakaoTokenResponse(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                refresh_token=token_data.get("refresh_token"),
                expires_in=token_data.get("expires_in", 0),
                scope=token_data.get("scope"),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid authorization code or expired code",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to exchange code for token",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to connect to Kakao API",
            )


async def get_kakao_user_info(access_token: str) -> KakaoUserInfo:
    """카카오 액세스 토큰을 사용하여 사용자 정보를 조회합니다."""
    settings = get_settings()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                settings.kakao.user_info_url,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            user_data = response.json()

            return KakaoUserInfo(
                id=user_data["id"],
                connected_at=user_data["connected_at"],
                properties=user_data.get("properties", {}),
                kakao_account=user_data.get("kakao_account", {}),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired access token",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get user info from Kakao",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to connect to Kakao API",
            )
