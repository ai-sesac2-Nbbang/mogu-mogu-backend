from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import api_messages, deps
from app.core.database_session import get_async_session
from app.enums import ParticipationStatusEnum, PostStatusEnum
from app.models import MoguFavorite, MoguPost, MoguPostImage, Participation, User
from app.schemas.requests import (
    MoguPostCreateRequest,
    MoguPostListQueryParams,
    MoguPostUpdateRequest,
)
from app.schemas.responses import (
    MoguPostListItemResponse,
    MoguPostListPaginatedResponse,
    MoguPostResponse,
    MoguPostWithParticipationPaginatedResponse,
    MoguPostWithParticipationResponse,
)

router = APIRouter()


async def _handle_post_status_change(
    mogu_post: MoguPost,
    original_status: PostStatusEnum,
    new_status: PostStatusEnum,
    session: AsyncSession,
) -> None:
    """모구 게시물 상태 변경 시 참여자들의 상태를 적절히 처리합니다."""

    # 게시물이 취소되거나 완료된 경우 참여자 상태 처리
    if new_status in [PostStatusEnum.CANCELED, PostStatusEnum.COMPLETED]:
        # 모든 참여자 조회
        participants_query = select(Participation).where(
            Participation.mogu_post_id == mogu_post.id
        )
        participants_result = await session.execute(participants_query)
        participants = participants_result.scalars().all()

        for participation in participants:
            if new_status == PostStatusEnum.CANCELED:
                # 게시물 취소 시: 모든 참여자 → CANCELED
                if participation.status == ParticipationStatusEnum.ACCEPTED:
                    # joined_count 감소 (ACCEPTED 참여자만)
                    mogu_post.joined_count -= 1

                participation.status = ParticipationStatusEnum.CANCELED
                participation.decided_at = datetime.utcnow()

            elif new_status == PostStatusEnum.COMPLETED:
                # 게시물 완료 시: ACCEPTED → FULFILLED (기본), APPLIED → CANCELED
                # 노쇼 처리는 별도 API에서 진행 (평가 시점 등)
                if participation.status == ParticipationStatusEnum.ACCEPTED:
                    participation.status = ParticipationStatusEnum.FULFILLED
                    participation.decided_at = datetime.utcnow()
                elif participation.status == ParticipationStatusEnum.APPLIED:
                    # 미처리 참여 요청은 취소 처리
                    participation.status = ParticipationStatusEnum.CANCELED
                    participation.decided_at = datetime.utcnow()


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

    # 기본 쿼리 - 썸네일 이미지만 로드
    query = select(MoguPost).options(
        selectinload(MoguPost.images),
    )

    # 필터 적용
    if params.category:
        query = query.where(MoguPost.category == params.category)
    if params.mogu_market:
        query = query.where(MoguPost.mogu_market == params.mogu_market)
    if params.status:
        query = query.where(MoguPost.status == params.status)

    # 거리 기반 필터링 (PostGIS 사용) - 이제 필수 파라미터
    query = query.where(
        func.ST_DWithin(
            MoguPost.mogu_spot,
            func.ST_SetSRID(func.ST_MakePoint(params.longitude, params.latitude), 4326),
            params.radius * 1000,  # km를 m로 변환
        )
    )

    # 정렬 적용
    if params.sort == "recent":
        query = query.order_by(desc(MoguPost.created_at))
    elif params.sort == "distance":
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
    posts = []
    for post in mogu_posts:
        # 찜하기 개수 조회
        favorite_count_query = (
            select(func.count())
            .select_from(MoguFavorite)
            .where(MoguFavorite.mogu_post_id == post.id)
        )
        favorite_count_result = await session.execute(favorite_count_query)
        favorite_count = favorite_count_result.scalar() or 0

        # 썸네일 이미지 추출
        thumbnail_image = None
        if post.images:
            # 썸네일 이미지 찾기
            thumbnail_img = next((img for img in post.images if img.is_thumbnail), None)
            if thumbnail_img:
                thumbnail_image = thumbnail_img.image_url
            else:
                # 썸네일이 없으면 첫 번째 이미지 사용
                thumbnail_image = post.images[0].image_url

        posts.append(
            MoguPostListItemResponse(
                id=post.id,
                title=post.title,
                price=post.price,
                category=post.category,
                mogu_market=post.mogu_market,
                mogu_datetime=post.mogu_datetime,
                status=(
                    post.status.value
                    if hasattr(post.status, "value")
                    else str(post.status)
                ),
                target_count=post.target_count or 0,
                joined_count=post.joined_count,
                created_at=post.created_at,
                thumbnail_image=thumbnail_image,
                favorite_count=favorite_count,
            )
        )

    return MoguPostListPaginatedResponse(
        posts=posts,
        pagination={
            "page": params.page,
            "limit": params.size,
            "total": total,
            "total_pages": (total + params.size - 1) // params.size,
        },
    )


@router.get(
    "/my-posts",
    response_model=MoguPostListPaginatedResponse,
    description="내가 작성한 게시물 목록",
)
async def get_my_posts(
    status: str | None = None,
    page: int = 1,
    size: int = 20,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> MoguPostListPaginatedResponse:
    """내가 작성한 모구 게시물 목록을 조회합니다."""

    # 기본 쿼리 구성
    query = (
        select(MoguPost)
        .where(MoguPost.user_id == current_user.id)
        .options(selectinload(MoguPost.images))
    )

    # 상태 필터 적용
    if status:
        try:
            status_enum = PostStatusEnum(status)
            query = query.where(MoguPost.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.INVALID_STATUS_VALUE,
            )

    # 정렬 (최신순)
    query = query.order_by(desc(MoguPost.created_at))

    # 전체 개수 조회
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # 페이지네이션 적용
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    # 쿼리 실행
    result = await session.execute(query)
    posts = result.scalars().all()

    # 응답 데이터 구성
    posts_list = []
    for post in posts:
        # 찜하기 개수 조회
        favorite_count_query = (
            select(func.count())
            .select_from(MoguFavorite)
            .where(MoguFavorite.mogu_post_id == post.id)
        )
        favorite_count_result = await session.execute(favorite_count_query)
        favorite_count = favorite_count_result.scalar() or 0

        # 썸네일 이미지 추출
        thumbnail_image = None
        if post.images:
            # 썸네일 이미지 찾기
            thumbnail_img = next((img for img in post.images if img.is_thumbnail), None)
            if thumbnail_img:
                thumbnail_image = thumbnail_img.image_url
            else:
                # 썸네일이 없으면 첫 번째 이미지 사용
                thumbnail_image = post.images[0].image_url

        posts_list.append(
            MoguPostListItemResponse(
                id=post.id,
                title=post.title,
                price=post.price,
                category=post.category,
                mogu_market=post.mogu_market,
                mogu_datetime=post.mogu_datetime,
                status=(
                    post.status.value
                    if hasattr(post.status, "value")
                    else str(post.status)
                ),
                target_count=post.target_count or 0,
                joined_count=post.joined_count,
                created_at=post.created_at,
                thumbnail_image=thumbnail_image,
                favorite_count=favorite_count,
            )
        )

    return MoguPostListPaginatedResponse(
        posts=posts_list,
        pagination={
            "page": page,
            "limit": size,
            "total": total,
            "total_pages": (total + size - 1) // size,
        },
    )


@router.get(
    "/my-participations",
    response_model=MoguPostWithParticipationPaginatedResponse,
    description="내가 참여한 게시물 목록",
)
async def get_my_participations(
    status: str | None = None,
    page: int = 1,
    size: int = 20,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> MoguPostWithParticipationPaginatedResponse:
    """내가 참여한 모구 게시물 목록을 조회합니다."""

    # 기본 쿼리 구성 (참여 테이블과 조인)
    query = (
        select(MoguPost, Participation)
        .join(Participation, MoguPost.id == Participation.mogu_post_id)
        .where(Participation.user_id == current_user.id)
        .options(selectinload(MoguPost.images))
    )

    # 상태 필터 적용
    if status:
        try:
            status_enum = ParticipationStatusEnum(status)
            query = query.where(Participation.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid participation status value",
            )

    # 정렬 (참여 신청일 최신순)
    query = query.order_by(desc(Participation.applied_at))

    # 전체 개수 조회
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # 페이지네이션 적용
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    # 쿼리 실행
    result = await session.execute(query)
    rows = result.all()

    # 응답 데이터 구성
    posts_list: list[MoguPostWithParticipationResponse] = []
    for post, participation in rows:
        # 찜하기 개수 조회
        favorite_count_query = (
            select(func.count())
            .select_from(MoguFavorite)
            .where(MoguFavorite.mogu_post_id == post.id)
        )
        favorite_count_result = await session.execute(favorite_count_query)
        favorite_count = favorite_count_result.scalar() or 0

        # 썸네일 이미지 추출
        thumbnail_image = None
        if post.images:
            # 썸네일 이미지 찾기
            thumbnail_img = next((img for img in post.images if img.is_thumbnail), None)
            if thumbnail_img:
                thumbnail_image = thumbnail_img.image_url
            else:
                # 썸네일이 없으면 첫 번째 이미지 사용
                thumbnail_image = post.images[0].image_url

        posts_list.append(
            MoguPostWithParticipationResponse(
                id=post.id,
                title=post.title,
                price=post.price,
                category=post.category,
                mogu_market=post.mogu_market,
                mogu_datetime=post.mogu_datetime,
                status=(
                    post.status.value
                    if hasattr(post.status, "value")
                    else str(post.status)
                ),
                target_count=post.target_count or 0,
                joined_count=post.joined_count,
                created_at=post.created_at,
                thumbnail_image=thumbnail_image,
                favorite_count=favorite_count,
                # 참여 상태 정보
                my_participation_status=participation.status,
                my_participation_applied_at=participation.applied_at,
                my_participation_decided_at=participation.decided_at,
            )
        )

    return MoguPostWithParticipationPaginatedResponse(
        posts=posts_list,
        pagination={
            "page": page,
            "limit": size,
            "total": total,
            "total_pages": (total + size - 1) // size,
        },
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
            selectinload(MoguPost.questions_answers),
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
        questions_answers=(
            [
                {
                    "id": qa.id,
                    "questioner_id": qa.questioner_id,
                    "question": qa.question,
                    "answerer_id": qa.answerer_id,
                    "answer": qa.answer,
                    "is_private": qa.is_private,
                    "question_created_at": qa.question_created_at,
                    "answer_created_at": qa.answer_created_at,
                }
                for qa in mogu_post.questions_answers
            ]
            if mogu_post.questions_answers
            else None
        ),
    )


@router.patch(
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

    # 상태 변경 전 원래 상태 저장
    original_status = mogu_post.status

    for field, value in update_data.items():
        if field != "images" and hasattr(mogu_post, field):
            setattr(mogu_post, field, value)

    # 모구 게시물 상태가 변경된 경우 참여자 상태 처리
    if "status" in update_data and original_status != mogu_post.status:
        await _handle_post_status_change(
            mogu_post,
            PostStatusEnum(original_status),
            PostStatusEnum(mogu_post.status),
            session,
        )

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
