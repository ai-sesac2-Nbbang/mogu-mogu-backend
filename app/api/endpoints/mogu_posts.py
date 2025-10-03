from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import api_messages, deps
from app.core.database_session import get_async_session
from app.enums import PostStatusEnum
from app.models import MoguFavorite, MoguPost, MoguPostImage, Participation, User
from app.schemas.requests import (
    MoguPostCreateRequest,
    MoguPostListQueryParams,
    MoguPostUpdateRequest,
)
from app.schemas.responses import (
    MoguPostListPaginatedResponse,
    MoguPostListResponse,
    MoguPostResponse,
)

router = APIRouter()


@router.post("/", response_model=MoguPostResponse, description="모구 게시물 생성")
async def create_mogu_post(
    data: MoguPostCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> MoguPostResponse:
    """모구 게시물을 생성합니다."""

    # 모구 게시물 생성
    mogu_post = MoguPost(
        user_id=current_user.id,
        title=data.title,
        description=data.description,
        price=data.price,
        category=data.category,
        mogu_market=data.mogu_market,
        mogu_spot=from_shape(
            Point(data.mogu_spot.longitude, data.mogu_spot.latitude), srid=4326
        ),
        mogu_datetime=data.mogu_datetime,
        target_count=data.target_count,
        status=PostStatusEnum.RECRUITING,
        joined_count=0,
    )

    session.add(mogu_post)
    await session.flush()  # ID를 얻기 위해 flush

    # 이미지가 있는 경우 추가
    if data.images:
        for img_data in data.images:
            mogu_post_image = MoguPostImage(
                mogu_post_id=mogu_post.id,
                image_url=img_data.image_url,
                sort_order=img_data.sort_order,
                is_thumbnail=img_data.is_thumbnail,
            )
            session.add(mogu_post_image)

    await session.commit()
    await session.refresh(mogu_post)

    # 응답을 위해 관계 데이터 로드
    await session.refresh(mogu_post, ["images", "user"])

    # Shapely를 사용한 위도/경도 추출
    point = to_shape(mogu_post.mogu_spot)

    return MoguPostResponse(
        id=mogu_post.id,
        user_id=mogu_post.user_id,
        title=mogu_post.title,
        description=mogu_post.description,
        price=mogu_post.price,
        category=mogu_post.category,
        mogu_market=mogu_post.mogu_market,
        mogu_spot={
            "longitude": point.x,
            "latitude": point.y,
        },
        mogu_datetime=mogu_post.mogu_datetime,
        status=mogu_post.status,
        target_count=mogu_post.target_count,
        joined_count=mogu_post.joined_count,
        created_at=mogu_post.created_at,
        images=(
            [
                {
                    "id": img.id,
                    "image_url": img.image_url,
                    "sort_order": img.sort_order,
                    "is_thumbnail": img.is_thumbnail,
                }
                for img in mogu_post.images
            ]
            if mogu_post.images
            else None
        ),
        user={
            "id": mogu_post.user.id,
            "nickname": mogu_post.user.nickname,
            "profile_image_url": mogu_post.user.profile_image_url,
        },
        my_participation=None,  # 생성자는 자동으로 참여하지 않음
        is_favorited=False,  # 새로 생성된 게시물은 찜하지 않음
    )


@router.get(
    "/",
    response_model=MoguPostListPaginatedResponse,
    description="모구 게시물 목록 조회",
)
async def get_mogu_posts(
    params: MoguPostListQueryParams = Depends(),
    current_user: User | None = Depends(deps.get_current_user_optional),
    session: AsyncSession = Depends(get_async_session),
) -> MoguPostListPaginatedResponse:
    """모구 게시물 목록을 조회합니다."""

    # 기본 쿼리
    query = select(MoguPost).options(
        selectinload(MoguPost.images),
        selectinload(MoguPost.user),
    )

    # 필터 적용
    if params.category:
        query = query.where(MoguPost.category == params.category)
    if params.mogu_market:
        query = query.where(MoguPost.mogu_market == params.mogu_market)
    if params.status:
        query = query.where(MoguPost.status == params.status)

    # 거리 기반 필터링 (PostGIS 사용)
    if params.latitude is not None and params.longitude is not None:
        query = query.where(
            func.ST_DWithin(
                MoguPost.mogu_spot,
                func.ST_SetSRID(
                    func.ST_MakePoint(params.longitude, params.latitude), 4326
                ),
                params.radius * 1000,  # km를 m로 변환
            )
        )

    # 정렬 적용
    if params.sort == "recent":
        query = query.order_by(desc(MoguPost.created_at))
    elif (
        params.sort == "distance"
        and params.latitude is not None
        and params.longitude is not None
    ):
        # 거리순 정렬 (PostGIS 사용)
        query = query.order_by(
            func.ST_Distance(
                MoguPost.mogu_spot,
                func.ST_SetSRID(
                    func.ST_MakePoint(params.longitude, params.latitude), 4326
                ),
            )
        )
    else:  # ai_recommended (기본값)
        # TODO: AI 추천 로직 구현
        query = query.order_by(desc(MoguPost.created_at))

    # 총 개수 조회
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # 페이지네이션 적용
    offset = (params.page - 1) * params.size
    query = query.offset(offset).limit(params.size)

    # 데이터 조회
    result = await session.execute(query)
    mogu_posts = result.scalars().all()

    # 응답 데이터 구성
    items = []
    for post in mogu_posts:
        # Shapely를 사용한 위도/경도 추출
        point = to_shape(post.mogu_spot)
        latitude = point.y
        longitude = point.x
        # 내 참여 상태 확인
        my_participation = None
        if current_user:
            participation_query = select(Participation).where(
                and_(
                    Participation.mogu_post_id == post.id,
                    Participation.user_id == current_user.id,
                )
            )
            participation_result = await session.execute(participation_query)
            participation = participation_result.scalar_one_or_none()

            if participation:
                my_participation = {
                    "status": participation.status,
                    "joined_at": participation.applied_at,
                }

        # 찜하기 상태 확인
        is_favorited = False
        if current_user:
            favorite_query = select(MoguFavorite).where(
                and_(
                    MoguFavorite.mogu_post_id == post.id,
                    MoguFavorite.user_id == current_user.id,
                )
            )
            favorite_result = await session.execute(favorite_query)
            is_favorited = favorite_result.scalar_one_or_none() is not None

        items.append(
            MoguPostListResponse(
                id=post.id,
                user_id=post.user_id,
                title=post.title,
                description=post.description,
                price=post.price,
                category=post.category,
                mogu_market=post.mogu_market,
                mogu_spot={
                    "latitude": latitude,
                    "longitude": longitude,
                },
                mogu_datetime=post.mogu_datetime,
                status=post.status,
                target_count=post.target_count,
                joined_count=post.joined_count,
                created_at=post.created_at,
                images=(
                    [
                        {
                            "id": img.id,
                            "image_url": img.image_url,
                            "sort_order": img.sort_order,
                            "is_thumbnail": img.is_thumbnail,
                        }
                        for img in post.images
                    ]
                    if post.images
                    else None
                ),
                user={
                    "id": post.user.id,
                    "nickname": post.user.nickname,
                    "profile_image_url": post.user.profile_image_url,
                },
                my_participation=my_participation,
                is_favorited=is_favorited,
            )
        )

    return MoguPostListPaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        size=params.size,
        has_next=offset + params.size < total,
    )


@router.get(
    "/{post_id}", response_model=MoguPostResponse, description="모구 게시물 상세 조회"
)
async def get_mogu_post(
    post_id: str,
    current_user: User | None = Depends(deps.get_current_user_optional),
    session: AsyncSession = Depends(get_async_session),
) -> MoguPostResponse:
    """모구 게시물을 상세 조회합니다."""

    # 게시물 조회
    query = (
        select(MoguPost)
        .options(
            selectinload(MoguPost.images),
            selectinload(MoguPost.user),
        )
        .where(MoguPost.id == post_id)
    )

    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # Shapely를 사용한 위도/경도 추출
    point = to_shape(mogu_post.mogu_spot)
    latitude = point.y
    longitude = point.x

    # 내 참여 상태 확인
    my_participation = None
    if current_user:
        participation_query = select(Participation).where(
            and_(
                Participation.mogu_post_id == post_id,
                Participation.user_id == current_user.id,
            )
        )
        participation_result = await session.execute(participation_query)
        participation = participation_result.scalar_one_or_none()

        if participation:
            my_participation = {
                "status": participation.status,
                "joined_at": participation.applied_at,
            }

    # 찜하기 상태 확인
    is_favorited = False
    if current_user:
        favorite_query = select(MoguFavorite).where(
            and_(
                MoguFavorite.mogu_post_id == post_id,
                MoguFavorite.user_id == current_user.id,
            )
        )
        favorite_result = await session.execute(favorite_query)
        is_favorited = favorite_result.scalar_one_or_none() is not None

    return MoguPostResponse(
        id=mogu_post.id,
        user_id=mogu_post.user_id,
        title=mogu_post.title,
        description=mogu_post.description,
        price=mogu_post.price,
        category=mogu_post.category,
        mogu_market=mogu_post.mogu_market,
        mogu_spot={
            "latitude": latitude,
            "longitude": longitude,
        },
        mogu_datetime=mogu_post.mogu_datetime,
        status=mogu_post.status,
        target_count=mogu_post.target_count,
        joined_count=mogu_post.joined_count,
        created_at=mogu_post.created_at,
        images=(
            [
                {
                    "id": img.id,
                    "image_url": img.image_url,
                    "sort_order": img.sort_order,
                    "is_thumbnail": img.is_thumbnail,
                }
                for img in mogu_post.images
            ]
            if mogu_post.images
            else None
        ),
        user={
            "id": mogu_post.user.id,
            "nickname": mogu_post.user.nickname,
            "profile_image_url": mogu_post.user.profile_image_url,
        },
        my_participation=my_participation,
        is_favorited=is_favorited,
    )


@router.put(
    "/{post_id}", response_model=MoguPostResponse, description="모구 게시물 수정"
)
async def update_mogu_post(
    post_id: str,
    data: MoguPostUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> MoguPostResponse:
    """모구 게시물을 수정합니다."""

    # 게시물 조회
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # 권한 확인 (작성자만 수정 가능)
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=api_messages.MOGU_POST_UPDATE_FORBIDDEN,
        )

    # 수정 가능한 상태인지 확인
    if mogu_post.status not in [
        PostStatusEnum.RECRUITING,
        PostStatusEnum.LOCKED,
    ]:
        raise HTTPException(
            status_code=400,
            detail=api_messages.MOGU_POST_UPDATE_NOT_ALLOWED,
        )

    # 필드 업데이트
    update_data = data.model_dump(exclude_unset=True)

    if "mogu_spot" in update_data:
        mogu_spot = update_data.pop("mogu_spot")
        mogu_post.mogu_spot = from_shape(
            Point(mogu_spot["longitude"], mogu_spot["latitude"]), srid=4326
        )

    for field, value in update_data.items():
        if field != "images" and hasattr(mogu_post, field):
            setattr(mogu_post, field, value)

    # 이미지 업데이트 (기존 이미지 삭제 후 새로 추가)
    if "images" in update_data:
        # 기존 이미지 삭제
        await session.execute(
            select(MoguPostImage).where(MoguPostImage.mogu_post_id == post_id)
        )
        delete_result = await session.execute(
            select(MoguPostImage).where(MoguPostImage.mogu_post_id == post_id)
        )
        existing_images = delete_result.scalars().all()
        for img in existing_images:
            await session.delete(img)

        # 새 이미지 추가
        for img_data in update_data["images"]:
            mogu_post_image = MoguPostImage(
                mogu_post_id=post_id,
                image_url=img_data["image_url"],
                sort_order=img_data["sort_order"],
                is_thumbnail=img_data["is_thumbnail"],
            )
            session.add(mogu_post_image)

    await session.commit()
    await session.refresh(mogu_post)

    # 응답을 위해 관계 데이터 로드
    await session.refresh(mogu_post, ["images", "user"])

    # Shapely를 사용한 위도/경도 추출
    point = to_shape(mogu_post.mogu_spot)

    return MoguPostResponse(
        id=mogu_post.id,
        user_id=mogu_post.user_id,
        title=mogu_post.title,
        description=mogu_post.description,
        price=mogu_post.price,
        category=mogu_post.category,
        mogu_market=mogu_post.mogu_market,
        mogu_spot={
            "latitude": point.y,
            "longitude": point.x,
        },
        mogu_datetime=mogu_post.mogu_datetime,
        status=mogu_post.status,
        target_count=mogu_post.target_count,
        joined_count=mogu_post.joined_count,
        created_at=mogu_post.created_at,
        images=(
            [
                {
                    "id": img.id,
                    "image_url": img.image_url,
                    "sort_order": img.sort_order,
                    "is_thumbnail": img.is_thumbnail,
                }
                for img in mogu_post.images
            ]
            if mogu_post.images
            else None
        ),
        user={
            "id": mogu_post.user.id,
            "nickname": mogu_post.user.nickname,
            "profile_image_url": mogu_post.user.profile_image_url,
        },
        my_participation=None,  # 수정 시에는 참여 상태를 다시 조회하지 않음
        is_favorited=False,  # 수정 시에는 찜하기 상태를 다시 조회하지 않음
    )


@router.delete("/{post_id}", description="모구 게시물 삭제")
async def delete_mogu_post(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """모구 게시물을 삭제합니다."""

    # 게시물 조회
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # 권한 확인 (작성자만 삭제 가능)
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=api_messages.MOGU_POST_DELETE_FORBIDDEN,
        )

    # 삭제 가능한 상태인지 확인
    if mogu_post.status not in [
        PostStatusEnum.RECRUITING,
        PostStatusEnum.LOCKED,
    ]:
        raise HTTPException(
            status_code=400,
            detail=api_messages.MOGU_POST_DELETE_NOT_ALLOWED,
        )

    # 게시물 삭제 (CASCADE로 관련 데이터도 함께 삭제됨)
    await session.delete(mogu_post)
    await session.commit()

    return {"message": "모구 게시물이 성공적으로 삭제되었습니다."}
