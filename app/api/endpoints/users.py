from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.enums import UserStatusEnum
from app.models import User, UserWishSpot
from app.schemas.requests import UserUpdateRequest, WishSpotCreateRequest
from app.schemas.responses import UserResponse, WishSpotResponse

router = APIRouter()

# 상수
MAX_WISH_SPOTS = 2


@router.get("/me", response_model=UserResponse, description="Get current user")
async def read_current_user(
    current_user: User = Depends(deps.get_current_user),
) -> UserResponse:
    return UserResponse(
        user_id=current_user.id,
        email=current_user.email,
        kakao_id=current_user.kakao_id,
        provider=current_user.provider,
        nickname=current_user.nickname,
        profile_image_url=current_user.profile_image_url,
        name=current_user.name,
        phone_number=current_user.phone_number,
        birth_date=current_user.birth_date,
        gender=current_user.gender,
        interested_categories=current_user.interested_categories,
        household_size=current_user.household_size,
        wish_markets=current_user.wish_markets,
        status=current_user.status,
        reported_count=current_user.reported_count,
        onboarded_at=current_user.onboarded_at,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


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

    # 온보딩 완료 체크: 필수 필드가 모두 채워졌는지 확인
    if current_user.status == UserStatusEnum.PENDING_ONBOARDING.value:
        if all(
            [
                current_user.name,
                current_user.phone_number,
                current_user.gender,
                current_user.household_size,
            ]
        ):
            current_user.status = UserStatusEnum.ACTIVE.value
            current_user.onboarded_at = datetime.utcnow()

    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    return UserResponse(
        user_id=current_user.id,
        email=current_user.email,
        kakao_id=current_user.kakao_id,
        provider=current_user.provider,
        nickname=current_user.nickname,
        profile_image_url=current_user.profile_image_url,
        name=current_user.name,
        phone_number=current_user.phone_number,
        birth_date=current_user.birth_date,
        gender=current_user.gender,
        interested_categories=current_user.interested_categories,
        household_size=current_user.household_size,
        wish_markets=current_user.wish_markets,
        status=current_user.status,
        reported_count=current_user.reported_count,
        onboarded_at=current_user.onboarded_at,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.get(
    "/me/wish-spots",
    response_model=list[WishSpotResponse],
    description="Get current user's wish spots",
)
async def get_wish_spots(
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> list[WishSpotResponse]:
    """현재 사용자의 관심 장소 목록 조회"""
    result = await session.execute(
        select(UserWishSpot)
        .where(UserWishSpot.user_id == current_user.id)
        .order_by(UserWishSpot.created_at)
    )
    spots = result.scalars().all()

    # Geography를 위도/경도로 변환
    response = []
    for spot in spots:
        point = to_shape(spot.location)
        response.append(
            WishSpotResponse(
                id=spot.id,
                label=spot.label,
                longitude=point.x,  # 경도
                latitude=point.y,  # 위도
                created_at=spot.created_at,
            )
        )

    return response


@router.post(
    "/me/wish-spots",
    status_code=status.HTTP_201_CREATED,
    description="Add wish spot (max 2)",
)
async def create_wish_spot(
    data: WishSpotCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> dict[str, str]:
    """관심 장소 추가 (최대 2개)"""
    # 기존 wish_spots 개수 확인
    result = await session.execute(
        select(UserWishSpot).where(UserWishSpot.user_id == current_user.id)
    )
    existing_spots = result.scalars().all()

    if len(existing_spots) >= MAX_WISH_SPOTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"최대 {MAX_WISH_SPOTS}개의 관심 장소만 등록할 수 있습니다.",
        )

    # PostGIS POINT 생성 (경도, 위도 순서!)
    point = Point(data.longitude, data.latitude)

    wish_spot = UserWishSpot(
        user_id=current_user.id,
        label=data.label,
        location=from_shape(point, srid=4326),
    )

    session.add(wish_spot)
    await session.commit()

    return {"message": "관심 장소가 추가되었습니다."}


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

    # 현재: 하드 삭제 (빠른 개발용)
    await session.execute(delete(User).where(User.id == current_user.id))
    await session.commit()
