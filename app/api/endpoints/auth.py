import secrets
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_messages, deps
from app.core.config import get_settings
from app.core.security.jwt import create_jwt_token
from app.core.security.kakao import exchange_code_for_token, get_kakao_user_info
from app.core.security.password import DUMMY_PASSWORD, verify_password
from app.models import RefreshToken, User
from app.schemas.requests import RefreshTokenRequest, UserCreateRequest
from app.schemas.responses import AccessTokenResponse, KakaoUserResponse, UserResponse

router = APIRouter()

ACCESS_TOKEN_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "description": "Invalid email or password",
        "content": {
            "application/json": {"example": {"detail": api_messages.PASSWORD_INVALID}}
        },
    },
}

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


@router.post(
    "/access-token",
    response_model=AccessTokenResponse,
    responses=ACCESS_TOKEN_RESPONSES,
    description="OAuth2 compatible token, get an access token for future requests using username and password",
)
async def login_access_token(
    session: AsyncSession = Depends(deps.get_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> AccessTokenResponse:
    user = await session.scalar(select(User).where(User.email == form_data.username))

    if user is None:
        # this is naive method to not return early
        verify_password(form_data.password, DUMMY_PASSWORD)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.PASSWORD_INVALID,
        )

    # 카카오 로그인만 사용하므로 비밀번호 검증 제거

    jwt_token = create_jwt_token(user_id=user.id)

    refresh_token = RefreshToken(
        user_id=user.id,
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


@router.post(
    "/register",
    response_model=UserResponse,
    description="Create new user",
    status_code=status.HTTP_201_CREATED,
)
async def register_new_user(
    new_user: UserCreateRequest,
    session: AsyncSession = Depends(deps.get_session),
) -> User:
    user = await session.scalar(select(User).where(User.email == new_user.email))
    if user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.EMAIL_ADDRESS_ALREADY_USED,
        )

    user = User(
        email=new_user.email,
        # hashed_password=get_password_hash(new_user.password),
    )
    session.add(user)

    try:
        await session.commit()
    except IntegrityError:  # pragma: no cover
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.EMAIL_ADDRESS_ALREADY_USED,
        )

    return user


@router.get(
    "/kakao/callback",
    description="카카오 로그인 콜백 - 인증 코드를 JWT 토큰으로 교환",
)
async def kakao_login_callback(
    code: str,
    state: str | None = None,
    session: AsyncSession = Depends(deps.get_session),
) -> RedirectResponse:
    """카카오 로그인 콜백 처리"""
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
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="카카오 계정에서 이메일 정보를 가져올 수 없습니다.",
                )

            # 이메일로 기존 사용자 확인
            existing_user = await session.scalar(
                select(User).where(User.email == email)
            )

            if existing_user:
                # 기존 사용자에 카카오 정보 연결
                existing_user.kakao_id = kakao_user_info.id
                existing_user.provider = "kakao"
                user = existing_user
            else:
                # 새 사용자 생성
                user = User(
                    email=email,
                    kakao_id=kakao_user_info.id,
                    provider="kakao",
                )
                session.add(user)
                await session.commit()
        else:
            # 기존 카카오 사용자
            session.add(user)
            await session.commit()

        # 4. JWT 토큰 생성
        jwt_token = create_jwt_token(user_id=user.id)

        # 5. 리프레시 토큰 생성
        refresh_token = RefreshToken(
            user_id=user.id,
            refresh_token=secrets.token_urlsafe(32),
            exp=int(time.time() + get_settings().security.refresh_token_expire_secs),
        )
        session.add(refresh_token)
        await session.commit()

        # 6. 사용자 정보 페이지로 리다이렉트 (토큰을 URL 파라미터로 전달)
        return RedirectResponse(
            url=f"/user?token={jwt_token.access_token}",
            status_code=status.HTTP_302_FOUND,
        )

    except HTTPException as e:
        # 에러 발생 시 로그인 페이지로 리다이렉트 (에러 메시지 포함)
        error_message = e.detail.replace(" ", "%20")
        return RedirectResponse(
            url=f"/login?error={error_message}", status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        # 예상치 못한 에러 발생 시 로그인 페이지로 리다이렉트
        error_message = f"카카오 로그인 처리 중 오류가 발생했습니다: {str(e)}".replace(
            " ", "%20"
        )
        return RedirectResponse(
            url=f"/login?error={error_message}", status_code=status.HTTP_302_FOUND
        )


@router.get(
    "/kakao/user",
    response_model=KakaoUserResponse,
    description="현재 로그인한 사용자의 카카오 정보 조회",
)
async def get_kakao_user_info_endpoint(
    current_user: User = Depends(deps.get_current_user),
) -> KakaoUserResponse:
    """현재 로그인한 사용자의 카카오 정보 조회"""
    if current_user.provider != "kakao" or not current_user.kakao_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="카카오로 로그인한 사용자가 아닙니다.",
        )

    return KakaoUserResponse(
        kakao_id=current_user.kakao_id,
        nickname=None,  # 필요시 카카오 API에서 추가 조회
        profile_image=None,  # 필요시 카카오 API에서 추가 조회
        email=current_user.email,
        connected_at=(current_user.created_at.isoformat()),
    )
