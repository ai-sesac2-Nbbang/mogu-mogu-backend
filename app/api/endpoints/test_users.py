import secrets
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database_session import get_async_session
from app.core.security.jwt import create_jwt_token
from app.enums import UserStatusEnum
from app.models import RefreshToken, User
from app.schemas.responses import AccessTokenResponse, UserResponse

router = APIRouter()

# 개발 환경에서만 Swagger에 노출
_is_development = get_settings().environment.lower() in [
    "development",
    "dev",
    "local",
]

# 테스트용 카카오 ID
TEST_KAKAO_ID = 999999999


@router.post(
    "/test-user", response_model=UserResponse, include_in_schema=_is_development
)
async def create_test_user(
    nickname: str = "테스트사용자",
    session: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """테스트용 사용자를 생성합니다."""

    # 테스트용 이메일 생성
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    email = f"test_{timestamp}@example.com"

    # 사용자 생성
    test_user = User(
        email=email,
        kakao_id=TEST_KAKAO_ID,  # 테스트용 카카오 ID
        provider="kakao",
        nickname=nickname,
        profile_image_url="https://example.com/test-profile.jpg",
        status=UserStatusEnum.ACTIVE.value,
        onboarded_at=datetime.utcnow(),
    )

    session.add(test_user)
    await session.commit()
    await session.refresh(test_user)

    return UserResponse(
        user_id=test_user.id,
        email=test_user.email,
        kakao_id=test_user.kakao_id,
        provider=test_user.provider,
        nickname=test_user.nickname,
        profile_image_url=test_user.profile_image_url,
        status=test_user.status,
        reported_count=test_user.reported_count,
        created_at=test_user.created_at,
        updated_at=test_user.updated_at,
        onboarded_at=test_user.onboarded_at,
    )


@router.post(
    "/test-token", response_model=AccessTokenResponse, include_in_schema=_is_development
)
async def create_test_token(
    user_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> AccessTokenResponse:
    """특정 사용자 ID로 테스트용 액세스 토큰을 생성합니다."""

    # 사용자 조회
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    # 기존 리프레시 토큰 삭제
    await session.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
    delete_result = await session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    )
    existing_tokens = delete_result.scalars().all()
    for token in existing_tokens:
        await session.delete(token)

    # 새 토큰 생성
    jwt_token = create_jwt_token(user_id=user.id)
    access_token = jwt_token.access_token

    # 리프레시 토큰 생성
    refresh_token = secrets.token_urlsafe(32)

    # 리프레시 토큰 저장
    refresh_token_obj = RefreshToken(
        refresh_token=refresh_token,
        user_id=user.id,
        exp=int(time.time() + get_settings().security.refresh_token_expire_secs),
    )

    session.add(refresh_token_obj)
    await session.commit()

    return AccessTokenResponse(
        token_type="Bearer",
        access_token=access_token,
        expires_at=jwt_token.payload.exp,
        refresh_token=refresh_token,
        refresh_token_expires_at=refresh_token_obj.exp,
    )


@router.post(
    "/test-user-with-token",
    response_model=dict[str, Any],
    include_in_schema=_is_development,
)
async def create_test_user_with_token(
    nickname: str = "테스트사용자",
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """테스트용 사용자를 생성하고 바로 토큰을 발급합니다."""

    # 1. 테스트 사용자 생성
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    email = f"test_{timestamp}@example.com"

    test_user = User(
        email=email,
        kakao_id=TEST_KAKAO_ID,
        provider="kakao",
        nickname=nickname,
        profile_image_url="https://example.com/test-profile.jpg",
        status=UserStatusEnum.ACTIVE.value,
        onboarded_at=datetime.utcnow(),
    )

    session.add(test_user)
    await session.commit()
    await session.refresh(test_user)

    # 2. 토큰 생성
    jwt_token = create_jwt_token(user_id=test_user.id)
    access_token = jwt_token.access_token

    # 리프레시 토큰 생성
    refresh_token = secrets.token_urlsafe(32)

    # 리프레시 토큰 저장
    refresh_token_obj = RefreshToken(
        refresh_token=refresh_token,
        user_id=test_user.id,
        exp=int(time.time() + get_settings().security.refresh_token_expire_secs),
    )

    session.add(refresh_token_obj)
    await session.commit()

    return {
        "user": {
            "user_id": test_user.id,
            "email": test_user.email,
            "nickname": test_user.nickname,
            "profile_image_url": test_user.profile_image_url,
        },
        "tokens": {
            "token_type": "Bearer",
            "access_token": access_token,
            "expires_at": jwt_token.payload.exp,
            "refresh_token": refresh_token,
            "refresh_token_expires_at": refresh_token_obj.exp,
        },
    }


@router.get("/test-users", include_in_schema=_is_development)
async def list_test_users(
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """테스트용 사용자 목록을 조회합니다."""

    query = (
        select(User)
        .where(User.kakao_id == TEST_KAKAO_ID)
        .order_by(User.created_at.desc())
    )
    result = await session.execute(query)
    users = result.scalars().all()

    return [
        {
            "user_id": user.id,
            "email": user.email,
            "nickname": user.nickname,
            "profile_image_url": user.profile_image_url,
            "created_at": user.created_at,
            "onboarded_at": user.onboarded_at,
        }
        for user in users
    ]


@router.delete("/test-user/{user_id}", include_in_schema=_is_development)
async def delete_test_user(
    user_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """테스트용 사용자를 삭제합니다."""

    # 사용자 조회
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    # 테스트용 사용자인지 확인
    if user.kakao_id != TEST_KAKAO_ID:
        raise HTTPException(status_code=400, detail="테스트용 사용자가 아닙니다.")

    # 사용자 삭제 (관련 데이터는 CASCADE로 자동 삭제)
    await session.delete(user)
    await session.commit()

    return {"message": "테스트 사용자가 삭제되었습니다."}
