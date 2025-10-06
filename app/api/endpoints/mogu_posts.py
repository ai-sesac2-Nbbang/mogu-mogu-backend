import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.api.common import (
    _build_mogu_post_basic_data,
    _calculate_pagination_info,
    _check_favorite_status,
    _check_post_permissions,
    _check_user_participation_status,
    _execute_paginated_query,
    _get_mogu_post,
    _get_mogu_post_with_relations,
    _get_user_participation_status,
    _validate_post_status_for_deletion,
)
from app.api.endpoints.ratings import _check_rating_completion, _check_rating_deadline
from app.core.database_session import get_async_session
from app.core.supabase import get_supabase_storage
from app.enums import ParticipationStatusEnum, PostStatusEnum
from app.models import MoguPost, MoguPostImage, Participation, User
from app.schemas.requests import (
    MoguPostCreateRequest,
    MoguPostListQueryParams,
    MoguPostUpdateRequest,
)
from app.schemas.responses import (
    MoguPostListItemResponse,
    MoguPostListItemWithReviewResponse,
    MoguPostListPaginatedResponse,
    MoguPostListWithReviewPaginatedResponse,
    MoguPostResponse,
    MoguPostWithParticipationPaginatedResponse,
    MoguPostWithParticipationResponse,
    QuestionAnswerConverter,
)
from app.schemas.types import ParticipationStatusLiteral, PostStatusLiteral

logger = logging.getLogger(__name__)

router = APIRouter()


# 기타 헬퍼 함수들


async def _can_user_review_post(
    mogu_post: MoguPost, current_user: User, session: AsyncSession
) -> bool:
    """사용자가 해당 게시물에 대해 리뷰를 작성할 수 있는지 확인합니다."""

    # 완료된 모구만 리뷰 가능
    if mogu_post.status != "completed":
        return False

    # 평가 작성 기한 확인
    is_within_deadline, _ = await _check_rating_deadline(mogu_post)
    if not is_within_deadline:
        return False

    # 모구장/참여자 확인
    is_mogu_leader, is_participant, _ = await _check_user_participation_status(
        mogu_post, current_user.id, session
    )

    # 평가 권한 확인
    if not is_mogu_leader and not is_participant:
        return False

    # 평가 완료 여부 확인
    all_ratings_completed = await _check_rating_completion(mogu_post, session)

    return not all_ratings_completed


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


@router.post(
    "/",
    response_model=MoguPostResponse,
    status_code=http_status.HTTP_201_CREATED,
    description="모구 게시물 생성",
)
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
                image_path=img_data.image_path,
                sort_order=img_data.sort_order,
                is_thumbnail=img_data.is_thumbnail,
            )
            session.add(mogu_post_image)

    await session.commit()
    await session.refresh(mogu_post)

    # 응답을 위해 관계 데이터 로드
    await session.refresh(mogu_post, ["images", "user"])

    return MoguPostResponse.from_mogu_post(
        mogu_post=mogu_post,
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
                func.ST_SetSRID(
                    func.ST_MakePoint(params.longitude, params.latitude), 4326
                ),
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
        # 게시물 기본 데이터 구성
        basic_data = await _build_mogu_post_basic_data(post, session)

        posts.append(
            MoguPostListItemResponse(
                id=post.id,
                title=post.title,
                price=post.price,
                labor_fee=post.labor_fee,
                category=post.category,
                mogu_market=post.mogu_market,
                mogu_datetime=post.mogu_datetime,
                status=post.status,
                target_count=post.target_count or 0,
                joined_count=post.joined_count,
                created_at=post.created_at,
                thumbnail_image=basic_data["thumbnail_image"],
                favorite_count=basic_data["favorite_count"],
            )
        )

    return MoguPostListPaginatedResponse(
        items=posts,
        pagination={
            "page": params.page,
            "limit": params.size,
            "total": total,
            "total_pages": (total + params.size - 1) // params.size,
        },
    )


@router.get(
    "/my-posts",
    response_model=MoguPostListWithReviewPaginatedResponse,
    description="내가 작성한 게시물 목록",
)
async def get_my_posts(
    status: PostStatusLiteral | None = None,
    page: int = 1,
    size: int = 20,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> MoguPostListWithReviewPaginatedResponse:
    """내가 작성한 모구 게시물 목록을 조회합니다."""

    # 기본 쿼리 구성
    query = (
        select(MoguPost)
        .where(MoguPost.user_id == current_user.id)
        .options(selectinload(MoguPost.images))
    )

    # 상태 필터 적용
    if status:
        query = query.where(MoguPost.status == status)

    # 정렬 (최신순)
    query = query.order_by(desc(MoguPost.created_at))

    # 페이지네이션 적용된 쿼리 실행
    result, total = await _execute_paginated_query(query, page, size, session)
    posts = result.scalars().all()

    # 응답 데이터 구성
    posts_list = []
    for post in posts:
        # 게시물 기본 데이터 구성
        basic_data = await _build_mogu_post_basic_data(post, session)

        # 리뷰 가능 여부 확인
        can_review = await _can_user_review_post(post, current_user, session)

        posts_list.append(
            MoguPostListItemWithReviewResponse(
                id=post.id,
                title=post.title,
                price=post.price,
                labor_fee=post.labor_fee,
                category=post.category,
                mogu_market=post.mogu_market,
                mogu_datetime=post.mogu_datetime,
                status=post.status,
                target_count=post.target_count or 0,
                joined_count=post.joined_count,
                created_at=post.created_at,
                thumbnail_image=basic_data["thumbnail_image"],
                favorite_count=basic_data["favorite_count"],
                can_review=can_review,
            )
        )

    return MoguPostListWithReviewPaginatedResponse(
        items=posts_list,
        pagination=await _calculate_pagination_info(page, size, total),
    )


@router.get(
    "/my-participations",
    response_model=MoguPostWithParticipationPaginatedResponse,
    description="내가 참여한 게시물 목록",
)
async def get_my_participations(
    status: ParticipationStatusLiteral | None = None,
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
        query = query.where(Participation.status == status)

    # 정렬 (참여 신청일 최신순)
    query = query.order_by(desc(Participation.applied_at))

    # 페이지네이션 적용된 쿼리 실행
    result, total = await _execute_paginated_query(query, page, size, session)
    rows = result.all()

    # 응답 데이터 구성
    posts_list: list[MoguPostWithParticipationResponse] = []
    for post, participation in rows:
        # 게시물 기본 데이터 구성
        basic_data = await _build_mogu_post_basic_data(post, session)

        # 리뷰 가능 여부 확인
        can_review = await _can_user_review_post(post, current_user, session)

        posts_list.append(
            MoguPostWithParticipationResponse(
                id=post.id,
                title=post.title,
                price=post.price,
                labor_fee=post.labor_fee,
                category=post.category,
                mogu_market=post.mogu_market,
                mogu_datetime=post.mogu_datetime,
                status=post.status,
                target_count=post.target_count or 0,
                joined_count=post.joined_count,
                created_at=post.created_at,
                thumbnail_image=basic_data["thumbnail_image"],
                favorite_count=basic_data["favorite_count"],
                can_review=can_review,
                # 참여 상태 정보
                my_participation_status=participation.status,
                my_participation_applied_at=participation.applied_at,
                my_participation_decided_at=participation.decided_at,
            )
        )

    return MoguPostWithParticipationPaginatedResponse(
        items=posts_list,
        pagination=await _calculate_pagination_info(page, size, total),
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

    # 게시물 조회 (관계 데이터 포함)
    mogu_post = await _get_mogu_post_with_relations(post_id, session)

    # 내 참여 상태 확인
    my_participation = None
    is_favorited = False
    if current_user:
        my_participation = await _get_user_participation_status(
            post_id, current_user.id, session
        )
        is_favorited = await _check_favorite_status(post_id, current_user.id, session)

    # Q&A 데이터 변환
    questions_answers = QuestionAnswerConverter.to_dict_list(
        mogu_post.questions_answers
    )

    return MoguPostResponse.from_mogu_post(
        mogu_post=mogu_post,
        my_participation=my_participation,
        is_favorited=is_favorited,
        questions_answers=questions_answers,
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
    mogu_post = await _get_mogu_post(post_id, session)

    # 권한 확인 (작성자만 수정 가능)
    await _check_post_permissions(mogu_post, current_user)

    # 수정 가능한 상태인지 확인
    await _validate_post_status_for_deletion(mogu_post)

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
                image_path=img_data["image_path"],
                sort_order=img_data["sort_order"],
                is_thumbnail=img_data["is_thumbnail"],
            )
            session.add(mogu_post_image)

    await session.commit()
    await session.refresh(mogu_post)

    # 응답을 위해 관계 데이터 로드
    await session.refresh(mogu_post, ["images", "user"])

    return MoguPostResponse.from_mogu_post(
        mogu_post=mogu_post,
        my_participation=None,  # 수정 시에는 참여 상태를 다시 조회하지 않음
        is_favorited=False,  # 수정 시에는 찜하기 상태를 다시 조회하지 않음
    )


@router.delete(
    "/{post_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    description="모구 게시물 삭제",
)
async def delete_mogu_post(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """모구 게시물을 삭제합니다."""

    # 게시물 조회
    mogu_post = await _get_mogu_post(post_id, session)

    # 권한 확인 (작성자만 삭제 가능)
    await _check_post_permissions(mogu_post, current_user)

    # 삭제 가능한 상태인지 확인
    await _validate_post_status_for_deletion(mogu_post)

    # 이미지들을 Supabase Storage에서 배치 삭제
    if mogu_post.images:
        try:
            supabase_storage = get_supabase_storage()
            image_paths = [img.image_path for img in mogu_post.images]
            await supabase_storage.delete_files_batch("images", image_paths)
            logger.info(f"게시물 이미지 {len(image_paths)}개 배치 삭제 완료")
        except Exception as e:
            logger.warning(f"이미지 배치 삭제 실패: {str(e)}")

    # 게시물 삭제 (CASCADE로 관련 데이터도 함께 삭제됨)
    await session.delete(mogu_post)
    await session.commit()
