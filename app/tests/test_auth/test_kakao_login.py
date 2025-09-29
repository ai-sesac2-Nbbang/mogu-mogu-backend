from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security.kakao import KakaoTokenResponse, KakaoUserInfo


@pytest.mark.asyncio
async def test_kakao_login_callback_success(client: AsyncClient) -> None:
    """카카오 로그인 콜백 성공 테스트"""
    # Mock 카카오 API 응답
    mock_token_response = KakaoTokenResponse(
        access_token="mock_access_token",
        token_type="Bearer",
        refresh_token="mock_refresh_token",
        expires_in=3600,
        scope="profile_nickname profile_image account_email",
    )

    mock_user_info = KakaoUserInfo(
        id=123456789,
        connected_at="2024-01-01T00:00:00Z",
        properties={"nickname": "테스트사용자"},
        kakao_account={
            "email": "test@example.com",
            "email_verified": True,
            "profile": {
                "nickname": "테스트사용자",
                "profile_image_url": "https://example.com/profile.jpg",
            },
        },
    )

    with patch(
        "app.core.security.kakao.exchange_code_for_token",
        return_value=mock_token_response,
    ), patch(
        "app.core.security.kakao.get_kakao_user_info", return_value=mock_user_info
    ):

        response = await client.post(
            "/auth/kakao/callback",
            json={"code": "mock_authorization_code", "state": "mock_state"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "expires_at" in data
    assert "refresh_token_expires_at" in data


@pytest.mark.asyncio
async def test_kakao_login_callback_invalid_code(client: AsyncClient) -> None:
    """잘못된 인증 코드로 카카오 로그인 실패 테스트"""
    from fastapi import HTTPException

    with patch(
        "app.core.security.kakao.exchange_code_for_token",
        side_effect=HTTPException(status_code=400, detail="Invalid authorization code"),
    ):

        response = await client.post(
            "/auth/kakao/callback", json={"code": "invalid_code", "state": "mock_state"}
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_kakao_login_callback_no_email(client: AsyncClient) -> None:
    """이메일 정보가 없는 카카오 계정으로 로그인 실패 테스트"""
    mock_token_response = KakaoTokenResponse(
        access_token="mock_access_token",
        token_type="Bearer",
        expires_in=3600,
    )

    mock_user_info = KakaoUserInfo(
        id=123456789,
        connected_at="2024-01-01T00:00:00Z",
        properties={"nickname": "테스트사용자"},
        kakao_account={
            "profile": {
                "nickname": "테스트사용자",
                "profile_image_url": "https://example.com/profile.jpg",
            }
        },
    )

    with patch(
        "app.core.security.kakao.exchange_code_for_token",
        return_value=mock_token_response,
    ), patch(
        "app.core.security.kakao.get_kakao_user_info", return_value=mock_user_info
    ):

        response = await client.post(
            "/auth/kakao/callback",
            json={"code": "mock_authorization_code", "state": "mock_state"},
        )

    assert response.status_code == 400
    assert "이메일 정보를 가져올 수 없습니다" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_kakao_user_info_success(
    client: AsyncClient, test_user_kakao: dict
) -> None:
    """카카오 사용자 정보 조회 성공 테스트"""
    # 카카오 로그인한 사용자로 인증
    login_response = await client.post(
        "/auth/access-token",
        data={
            "username": test_user_kakao["email"],
            "password": test_user_kakao["password"],
        },
    )
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/auth/kakao/user", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "kakao_id" in data
    assert "email" in data
    assert "connected_at" in data


@pytest.mark.asyncio
async def test_get_kakao_user_info_not_kakao_user(
    client: AsyncClient, test_user: dict
) -> None:
    """카카오가 아닌 사용자가 카카오 정보 조회 시 실패 테스트"""
    # 일반 이메일 로그인한 사용자로 인증
    login_response = await client.post(
        "/auth/access-token",
        data={"username": test_user["email"], "password": test_user["password"]},
    )
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/auth/kakao/user", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 400
    assert "카카오로 로그인한 사용자가 아닙니다" in response.json()["detail"]
