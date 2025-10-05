from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.api.common import _get_mogu_post
from app.core.database_session import get_async_session
from app.models import MoguPost, Participation, Rating, RatingKeywordMaster, User
from app.schemas.requests import RatingCreateRequest, RatingUpdateRequest
from app.schemas.responses import (
    RatingKeywordListResponse,
    RatingKeywordMasterResponse,
    RatingListResponse,
    RatingResponse,
    RatingWithReviewerResponse,
    UserKeywordStatsResponse,
)

router = APIRouter()


async def _validate_rating_permissions(
    mogu_post: MoguPost,
    current_user: User,
    reviewee_id: str,
    session: AsyncSession,
) -> None:
    """평가 권한 및 대상 유효성을 검증합니다."""

    # 1. 자기 자신에게 평가하는 것 방지
    if current_user.id == reviewee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자기 자신에게는 평가를 작성할 수 없습니다.",
        )

    # 2. 모구장인지 확인
    is_mogu_leader = mogu_post.user_id == current_user.id

    # 3. 모구러인지 확인 (참여 상태가 accepted인 경우만)
    participation_query = select(Participation).where(
        and_(
            Participation.mogu_post_id == mogu_post.id,
            Participation.user_id == current_user.id,
            Participation.status == "accepted",
        )
    )
    participation_result = await session.execute(participation_query)
    participation = participation_result.scalar_one_or_none()
    is_participant = participation is not None

    # 4. 평가 권한 확인
    if not is_mogu_leader and not is_participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="모구장 또는 참여자만 평가를 작성할 수 있습니다.",
        )

    # 5. 평가 대상 유효성 확인
    if is_mogu_leader:
        # 모구장이 평가할 때: reviewee_id가 해당 모구의 참여자여야 함
        target_participation_query = select(Participation).where(
            and_(
                Participation.mogu_post_id == mogu_post.id,
                Participation.user_id == reviewee_id,
                Participation.status == "accepted",
            )
        )
        target_participation_result = await session.execute(target_participation_query)
        target_participation = target_participation_result.scalar_one_or_none()

        if not target_participation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="해당 사용자는 이 모구의 참여자가 아닙니다.",
            )
    elif not is_mogu_leader:
        # 모구러가 평가할 때: reviewee_id가 해당 모구의 모구장이어야 함
        if reviewee_id != mogu_post.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="참여자는 모구장에게만 평가를 작성할 수 있습니다.",
            )


async def _get_rating(
    post_id: str,
    rating_id: str,
    session: AsyncSession,
) -> Rating:
    """평가를 조회합니다."""
    rating_query = select(Rating).where(
        and_(
            Rating.id == rating_id,
            Rating.mogu_post_id == post_id,
        )
    )
    rating_result = await session.execute(rating_query)
    rating = rating_result.scalar_one_or_none()

    if not rating:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="평가를 찾을 수 없습니다.",
        )

    return rating


@router.post(
    "/{post_id}/ratings",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
    description="평가 작성",
)
async def create_rating(
    post_id: str,
    data: RatingCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> RatingResponse:
    """모구 게시물에 평가를 작성합니다."""

    # 게시물 조회 및 상태 확인
    mogu_post = await _get_mogu_post(post_id, session)

    # 모구 완료 상태 확인
    if mogu_post.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="완료된 모구에만 평가를 작성할 수 있습니다.",
        )

    # 평가 권한 및 대상 유효성 검증
    await _validate_rating_permissions(mogu_post, current_user, data.reviewee_id, session)

    # 중복 평가 방지
    existing_rating_query = select(Rating).where(
        and_(
            Rating.mogu_post_id == post_id,
            Rating.reviewer_id == current_user.id,
            Rating.reviewee_id == data.reviewee_id,
        )
    )
    existing_rating_result = await session.execute(existing_rating_query)
    existing_rating = existing_rating_result.scalar_one_or_none()

    if existing_rating:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 해당 사용자에게 평가를 작성했습니다.",
        )

    # 평가 생성
    rating = Rating(
        mogu_post_id=post_id,
        reviewer_id=current_user.id,
        reviewee_id=data.reviewee_id,
        stars=data.stars,
        keywords=data.keywords,
    )

    session.add(rating)
    await session.commit()
    await session.refresh(rating)

    return RatingResponse.from_rating(rating)


@router.get(
    "/{post_id}/ratings",
    response_model=RatingListResponse,
    description="평가 목록 조회",
)
async def get_ratings(
    post_id: str,
    current_user: User | None = Depends(deps.get_current_user_optional),
    session: AsyncSession = Depends(get_async_session),
) -> RatingListResponse:
    """모구 게시물의 평가 목록을 조회합니다."""

    # 게시물 존재 확인
    await _get_mogu_post(post_id, session)

    # 평가 목록 조회
    ratings_query = (
        select(Rating)
        .options(
            selectinload(Rating.reviewer),
        )
        .where(Rating.mogu_post_id == post_id)
        .order_by(Rating.created_at.desc())
    )

    ratings_result = await session.execute(ratings_query)
    ratings = ratings_result.scalars().all()

    ratings_data = [
        RatingWithReviewerResponse.from_rating(rating) for rating in ratings
    ]

    return RatingListResponse(items=ratings_data)


@router.patch(
    "/{post_id}/ratings/{rating_id}",
    response_model=RatingResponse,
    description="평가 수정",
)
async def update_rating(
    post_id: str,
    rating_id: str,
    data: RatingUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> RatingResponse:
    """평가를 수정합니다 (평가 작성자만)."""

    # 평가 조회
    rating = await _get_rating(post_id, rating_id, session)

    # 평가 작성자 권한 확인
    if rating.reviewer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="평가 작성자만 수정할 수 있습니다.",
        )

    # 평가 업데이트
    if data.stars is not None:
        rating.stars = data.stars
    if data.keywords is not None:
        rating.keywords = data.keywords

    await session.commit()
    await session.refresh(rating)

    return RatingResponse.from_rating(rating)


@router.delete(
    "/{post_id}/ratings/{rating_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="평가 삭제",
)
async def delete_rating(
    post_id: str,
    rating_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """평가를 삭제합니다 (평가 작성자만)."""

    # 평가 조회
    rating = await _get_rating(post_id, rating_id, session)

    # 평가 작성자 권한 확인
    if rating.reviewer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="평가 작성자만 삭제할 수 있습니다.",
        )

    # 평가 삭제
    await session.delete(rating)
    await session.commit()


@router.get(
    "/rating-keywords",
    response_model=RatingKeywordListResponse,
    description="평가 키워드 목록 조회",
)
async def get_rating_keywords(
    keyword_type: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> RatingKeywordListResponse:
    """평가 키워드 목록을 조회합니다."""

    # 키워드 목록 조회
    keywords_query = select(RatingKeywordMaster)

    if keyword_type:
        keywords_query = keywords_query.where(RatingKeywordMaster.type == keyword_type)

    keywords_query = keywords_query.order_by(RatingKeywordMaster.id)

    keywords_result = await session.execute(keywords_query)
    keywords = keywords_result.scalars().all()

    keywords_data = [
        RatingKeywordMasterResponse.from_keyword_master(keyword) for keyword in keywords
    ]

    return RatingKeywordListResponse(keywords=keywords_data)


@router.get(
    "/users/{user_id}/keyword-stats",
    response_model=UserKeywordStatsResponse,
    description="사용자 키워드 통계 조회",
)
async def get_user_keyword_stats(
    user_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> UserKeywordStatsResponse:
    """사용자의 키워드 통계를 조회합니다."""

    # 사용자 존재 확인
    user_query = select(User).where(User.id == user_id)
    user_result = await session.execute(user_query)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )

    # TODO: UserKeywordStats 모델이 구현되면 실제 통계 데이터 조회
    # 현재는 임시 데이터 반환
    return UserKeywordStatsResponse(
        user_id=user_id,
        keyword_code="temp",
        count=0,
        last_updated=datetime.utcnow(),
    )
