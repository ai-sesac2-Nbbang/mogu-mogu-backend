import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.supabase import get_supabase_storage
from app.enums import UserStatusEnum
from app.models import User, UserWishSpot
from app.schemas.requests import UserUpdateRequest, WishSpotCreateRequest
from app.schemas.responses import UserResponse, WishSpotListResponse, WishSpotResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# 상수
MAX_WISH_SPOTS = 2


# 공통 헬퍼 함수들


def _check_onboarding_completion(user: User) -> None:
    """온보딩 완료 여부를 확인하고 필요시 상태를 업데이트합니다."""
    if user.status == UserStatusEnum.PENDING_ONBOARDING.value:
        if all(
            [
                user.name,
                user.phone_number,
                user.gender,
                user.household_size,
            ]
        ):
            user.status = UserStatusEnum.ACTIVE.value
            user.onboarded_at = datetime.utcnow()


async def _get_user_wish_spots(
    user_id: str, session: AsyncSession
) -> list[UserWishSpot]:
    """사용자의 관심 장소 목록을 조회합니다."""
    result = await session.execute(
        select(UserWishSpot)
        .where(UserWishSpot.user_id == user_id)
        .order_by(UserWishSpot.created_at)
    )
    spots = result.scalars().all()
    return [spot for spot in spots]


def _build_wish_spot_response(spot: UserWishSpot) -> WishSpotResponse:
    """관심 장소 응답 객체를 생성합니다."""
    point = to_shape(spot.location)
    return WishSpotResponse(
        id=spot.id,
        label=spot.label,
        longitude=point.x,  # 경도
        latitude=point.y,  # 위도
        created_at=spot.created_at,
    )


async def _validate_wish_spot_limit(user_id: str, session: AsyncSession) -> None:
    """관심 장소 개수 제한을 검증합니다."""
    existing_spots = await _get_user_wish_spots(user_id, session)
    if len(existing_spots) >= MAX_WISH_SPOTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"최대 {MAX_WISH_SPOTS}개의 관심 장소만 등록할 수 있습니다.",
        )


@router.get("/me", response_model=UserResponse, description="Get current user")
async def read_current_user(
    current_user: User = Depends(deps.get_current_user),
) -> UserResponse:
    """현재 사용자 정보를 조회합니다."""
    return UserResponse.from_user(current_user)


@router.patch("/me", response_model=UserResponse, description="Update current user")
async def update_current_user(
    data: UserUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> UserResponse:
    """
    사용자 정보 업데이트 (온보딩 완료 포함)

    - 제공된 필드만 업데이트됨
    - 온보딩 필수 필드(name, phone_number, gender, household_size)가 모두 채워지면 status가 active로 변경됨
    """
    # 제공된 필드만 업데이트
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # 온보딩 완료 체크
    _check_onboarding_completion(current_user)

    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    return UserResponse.from_user(current_user)


@router.get(
    "/me/wish-spots",
    response_model=WishSpotListResponse,
    description="Get current user's wish spots",
)
async def get_wish_spots(
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> WishSpotListResponse:
    """현재 사용자의 관심 장소 목록 조회"""
    spots = await _get_user_wish_spots(current_user.id, session)
    return WishSpotListResponse(
        items=[_build_wish_spot_response(spot) for spot in spots]
    )


@router.post(
    "/me/wish-spots",
    status_code=status.HTTP_201_CREATED,
    response_model=WishSpotResponse,
    description="Add wish spot (max 2)",
)
async def create_wish_spot(
    data: WishSpotCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> WishSpotResponse:
    """관심 장소 추가 (최대 2개)"""
    # 관심 장소 개수 제한 검증
    await _validate_wish_spot_limit(current_user.id, session)

    # PostGIS POINT 생성 (경도, 위도 순서!)
    point = Point(data.longitude, data.latitude)

    wish_spot = UserWishSpot(
        user_id=current_user.id,
        label=data.label,
        location=from_shape(point, srid=4326),
    )

    session.add(wish_spot)
    await session.commit()
    await session.refresh(wish_spot)

    return _build_wish_spot_response(wish_spot)


@router.delete(
    "/me/wish-spots/{spot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Delete wish spot",
)
async def delete_wish_spot(
    spot_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> None:
    """관심 장소 삭제"""
    result = await session.execute(
        select(UserWishSpot).where(
            UserWishSpot.id == spot_id, UserWishSpot.user_id == current_user.id
        )
    )
    spot = result.scalar_one_or_none()

    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="관심 장소를 찾을 수 없습니다.",
        )

    await session.delete(spot)
    await session.commit()


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Delete current user (회원 탈퇴)",
)
async def delete_current_user(
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> None:
    """
    회원 탈퇴 (하드 삭제)

    TODO: Soft delete로 변경 필요
    - status를 inactive로 변경
    - deactivated_at 타임스탬프 추가
    - 재가입 정책 구현 (자동 복구 or 유예 기간)
    - 탈퇴 사용자 로그인/API 접근 차단
    """
    # TODO: 나중에 soft delete로 변경
    # current_user.status = UserStatusEnum.INACTIVE.value
    # current_user.deactivated_at = datetime.utcnow()
    # session.add(current_user)

    # 프로필 이미지가 있으면 Supabase Storage에서 삭제
    if current_user.profile_image_path:
        try:
            supabase_storage = get_supabase_storage()
            await supabase_storage.delete_files_batch(
                "images", [current_user.profile_image_path]
            )
        except Exception as e:
            # 이미지 삭제 실패해도 사용자 삭제는 진행
            logger.warning(
                f"프로필 이미지 삭제 실패: {current_user.profile_image_path}, 오류: {str(e)}"
            )

    # 현재: 하드 삭제 (빠른 개발용)
    await session.execute(delete(User).where(User.id == current_user.id))
    await session.commit()
