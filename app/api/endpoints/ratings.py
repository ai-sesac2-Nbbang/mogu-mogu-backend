from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.api.common import _get_mogu_post, _get_mogu_post_with_relations
from app.core.database_session import get_async_session
from app.models import MoguPost, Participation, Rating, RatingKeywordMaster, User
from app.schemas.requests import RatingCreateRequest, RatingUpdateRequest
from app.schemas.responses import (
    RatingKeywordListResponse,
    RatingKeywordMasterResponse,
    RatingListResponse,
    RatingResponse,
    RatingWithReviewerResponse,
    ReviewableUserResponse,
    ReviewableUsersResponse,
    UserKeywordStatsResponse,
)

router = APIRouter()

# rating-keywords 전용 라우터 (인증 불필요)
keywords_router = APIRouter()

# 평가 작성 기한 (거래 완료 후 3일)
RATING_DEADLINE_DAYS = 3


async def _check_rating_deadline(
    mogu_post: MoguPost,
) -> tuple[bool, dict[str, Any] | None]:
    """평가 작성 기한을 확인합니다."""

    # 모구 날짜를 거래 완료 날짜로 사용
    completed_at = mogu_post.mogu_datetime

    # 기한 계산 (거래 완료 후 3일)
    deadline = completed_at + timedelta(days=RATING_DEADLINE_DAYS)
    now = datetime.utcnow()

    # 시간대 정보 제거 (UTC로 통일)
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    if deadline.tzinfo is not None:
        deadline = deadline.replace(tzinfo=None)
    if completed_at.tzinfo is not None:
        completed_at = completed_at.replace(tzinfo=None)

    is_within_deadline = now <= deadline

    deadline_info = {
        "completed_at": completed_at.isoformat(),
        "deadline": deadline.isoformat(),
        "remaining_hours": max(0, int((deadline - now).total_seconds() / 3600)),
        "is_expired": not is_within_deadline,
    }

    return is_within_deadline, deadline_info


async def _validate_mogu_post_for_rating(
    post_id: str, session: AsyncSession, include_user_relation: bool = False
) -> MoguPost:
    """평가 관련 작업을 위한 모구 게시물 조회 및 검증"""
    if include_user_relation:
        mogu_post = await _get_mogu_post_with_relations(post_id, session)
    else:
        mogu_post = await _get_mogu_post(post_id, session)

    # 모구 완료 상태 확인
    if mogu_post.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="완료된 모구에만 평가를 작성할 수 있습니다.",
        )

    return mogu_post


async def _validate_rating_deadline(mogu_post: MoguPost, action: str = "평가") -> None:
    """평가 관련 작업의 기한을 확인합니다."""
    is_within_deadline, _ = await _check_rating_deadline(mogu_post)
    if not is_within_deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{action} 기한이 지났습니다. (거래 완료 후 {RATING_DEADLINE_DAYS}일 이내)",
        )


async def _check_rating_completion(
    mogu_post: MoguPost,
    session: AsyncSession,
) -> tuple[bool, dict[str, Any]]:
    """모든 필요한 평가가 완료되었는지 확인합니다."""

    # 1. 모구장과 모든 평가 대상 참여자 조회 (fulfilled + no_show)
    mogu_leader_id = mogu_post.user_id

    fulfilled_participants_query = select(Participation).where(
        and_(
            Participation.mogu_post_id == mogu_post.id,
            Participation.status.in_(["fulfilled", "no_show"]),
        )
    )
    fulfilled_participants_result = await session.execute(fulfilled_participants_query)
    fulfilled_participants = fulfilled_participants_result.scalars().all()

    # 2. 필요한 평가 관계 정의
    required_ratings = []

    # 모구장 → 각 참여자 평가
    for participant in fulfilled_participants:
        required_ratings.append(
            {
                "reviewer_id": mogu_leader_id,
                "reviewee_id": participant.user_id,
                "type": "leader_to_participant",
            }
        )

    # 각 참여자 → 모구장 평가
    for participant in fulfilled_participants:
        required_ratings.append(
            {
                "reviewer_id": participant.user_id,
                "reviewee_id": mogu_leader_id,
                "type": "participant_to_leader",
            }
        )

    # 3. 실제 작성된 평가 조회
    written_ratings_query = select(Rating).where(Rating.mogu_post_id == mogu_post.id)
    written_ratings_result = await session.execute(written_ratings_query)
    written_ratings = written_ratings_result.scalars().all()

    # 4. 완료된 평가 추적
    completed_ratings = []
    for rating in written_ratings:
        completed_ratings.append(
            {
                "reviewer_id": rating.reviewer_id,
                "reviewee_id": rating.reviewee_id,
            }
        )

    # 5. 완료 여부 확인
    all_ratings_completed = True
    missing_ratings = []

    for required_rating in required_ratings:
        is_completed = any(
            completed["reviewer_id"] == required_rating["reviewer_id"]
            and completed["reviewee_id"] == required_rating["reviewee_id"]
            for completed in completed_ratings
        )

        if not is_completed:
            all_ratings_completed = False
            missing_ratings.append(required_rating)

    # 6. 완료 정보 구성
    completion_info = {
        "is_all_ratings_completed": all_ratings_completed,
        "total_required_ratings": len(required_ratings),
        "total_completed_ratings": len(completed_ratings),
        "completion_percentage": (
            round((len(completed_ratings) / len(required_ratings)) * 100, 1)
            if required_ratings
            else 100
        ),
        "missing_ratings_count": len(missing_ratings),
        "participants_count": len(fulfilled_participants),
        "leader_id": mogu_leader_id,
    }

    return all_ratings_completed, completion_info


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

    # 3. 모구러인지 확인 (참여 상태가 fulfilled 또는 no_show인 경우)
    participation_query = select(Participation).where(
        and_(
            Participation.mogu_post_id == mogu_post.id,
            Participation.user_id == current_user.id,
            Participation.status.in_(["fulfilled", "no_show"]),
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
                Participation.status.in_(["fulfilled", "no_show"]),
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


async def _get_rating_by_id(
    rating_id: str,
    session: AsyncSession,
) -> Rating:
    """평가 ID로 평가를 조회합니다."""
    rating_query = select(Rating).where(Rating.id == rating_id)
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
    mogu_post = await _validate_mogu_post_for_rating(post_id, session)

    # 평가 작성 기한 확인
    await _validate_rating_deadline(mogu_post, "평가 작성")

    # 평가 권한 및 대상 유효성 검증
    await _validate_rating_permissions(
        mogu_post, current_user, data.reviewee_id, session
    )

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


@router.get(
    "/ratings/{rating_id}",
    response_model=RatingWithReviewerResponse,
    description="평가 상세 조회",
)
async def get_rating(
    rating_id: str,
    current_user: User | None = Depends(deps.get_current_user_optional),
    session: AsyncSession = Depends(get_async_session),
) -> RatingWithReviewerResponse:
    """평가 ID로 평가를 상세 조회합니다."""

    # 평가 조회
    rating = await _get_rating_by_id(rating_id, session)

    # 평가자 정보와 함께 반환
    return RatingWithReviewerResponse.from_rating(rating)


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

    # 모구 게시물 조회 및 기한 확인
    mogu_post = await _validate_mogu_post_for_rating(post_id, session)
    await _validate_rating_deadline(mogu_post, "평가 수정")

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

    # 모구 게시물 조회 및 기한 확인
    mogu_post = await _validate_mogu_post_for_rating(post_id, session)
    await _validate_rating_deadline(mogu_post, "평가 삭제")

    # 평가 삭제
    await session.delete(rating)
    await session.commit()


@keywords_router.get(
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


@router.get(
    "/{post_id}/reviewable-users",
    response_model=ReviewableUsersResponse,
    description="리뷰 가능한 사용자 목록 조회",
)
async def get_reviewable_users(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReviewableUsersResponse:
    """현재 사용자가 리뷰할 수 있는 사용자 목록을 조회합니다."""

    # 게시물 조회 (user 관계 포함) 및 상태 확인
    mogu_post = await _validate_mogu_post_for_rating(
        post_id, session, include_user_relation=True
    )

    # 평가 작성 기한 확인
    await _validate_rating_deadline(mogu_post, "평가 작성")

    # 모구장인지 확인
    is_mogu_leader = mogu_post.user_id == current_user.id

    # 모구러인지 확인 (fulfilled 또는 no_show 상태인 참여자)
    participation_query = select(Participation).where(
        and_(
            Participation.mogu_post_id == mogu_post.id,
            Participation.user_id == current_user.id,
            Participation.status.in_(["fulfilled", "no_show"]),
        )
    )
    participation_result = await session.execute(participation_query)
    participation = participation_result.scalar_one_or_none()
    is_participant = participation is not None

    # 평가 권한 확인
    if not is_mogu_leader and not is_participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="모구장 또는 완료된 참여자만 평가를 작성할 수 있습니다.",
        )

    # 리뷰 가능한 사용자 목록 조회
    reviewable_users = await _get_reviewable_users(
        mogu_post, current_user, is_mogu_leader, session
    )

    return ReviewableUsersResponse(items=reviewable_users)


async def _get_reviewable_users(
    mogu_post: MoguPost,
    current_user: User,
    is_mogu_leader: bool,
    session: AsyncSession,
) -> list[ReviewableUserResponse]:
    """리뷰 가능한 사용자 목록을 조회합니다."""

    reviewable_users = []

    if is_mogu_leader:
        # 모구장이 리뷰할 수 있는 사용자: fulfilled 또는 no_show 상태인 참여자들
        participations_query = (
            select(Participation)
            .options(selectinload(Participation.user))
            .where(
                and_(
                    Participation.mogu_post_id == mogu_post.id,
                    Participation.status.in_(["fulfilled", "no_show"]),
                )
            )
        )
        participations_result = await session.execute(participations_query)
        participations = participations_result.scalars().all()

        for participation in participations:
            # 이미 평가했는지 확인
            existing_rating_query = select(Rating).where(
                and_(
                    Rating.mogu_post_id == mogu_post.id,
                    Rating.reviewer_id == current_user.id,
                    Rating.reviewee_id == participation.user_id,
                )
            )
            existing_rating_result = await session.execute(existing_rating_query)
            existing_rating = existing_rating_result.scalar_one_or_none()

            reviewable_users.append(
                ReviewableUserResponse.from_participation(
                    participation,
                    rating_id=existing_rating.id if existing_rating else None,
                )
            )

    else:
        # 모구러가 리뷰할 수 있는 사용자: 모구장
        # 이미 평가했는지 확인
        existing_rating_query = select(Rating).where(
            and_(
                Rating.mogu_post_id == mogu_post.id,
                Rating.reviewer_id == current_user.id,
                Rating.reviewee_id == mogu_post.user_id,
            )
        )
        existing_rating_result = await session.execute(existing_rating_query)
        existing_rating = existing_rating_result.scalar_one_or_none()

        reviewable_users.append(
            ReviewableUserResponse.from_user(
                mogu_post.user,
                participation_status="mogu_leader",
                rating_id=existing_rating.id if existing_rating else None,
            )
        )

    return reviewable_users
