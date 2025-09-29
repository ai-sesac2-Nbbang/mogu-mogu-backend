from fastapi import APIRouter, Depends, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps

# 카카오 로그인만 사용하므로 비밀번호 관련 import 제거
from app.models import User

# 카카오 로그인만 사용하므로 비밀번호 관련 스키마 제거
from app.schemas.responses import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse, description="Get current user")
async def read_current_user(
    current_user: User = Depends(deps.get_current_user),
) -> UserResponse:
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        provider=current_user.provider,
        kakao_id=current_user.kakao_id,
        kakao_connected_at=current_user.created_at.isoformat(),
    )


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Delete current user",
)
async def delete_current_user(
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> None:
    await session.execute(delete(User).where(User.user_id == current_user.user_id))
    await session.commit()


# 카카오 로그인만 사용하므로 비밀번호 관련 기능 제거
