"""
사용자 통계 관련 API 엔드포인트
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_session import get_async_session
from app.models import Rating, RatingKeywordMaster, User
from app.schemas.responses import (
    RatingDistribution,
    UserKeywordStatsListResponse,
    UserKeywordStatsResponse,
    UserRatingStatsResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/users/{user_id}/stats/keywords",
    response_model=UserKeywordStatsListResponse,
    description="사용자 키워드 통계 조회",
)
async def get_user_keyword_stats(
    user_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> UserKeywordStatsListResponse:
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

    # Rating 테이블에서 실시간 키워드 통계 집계
    # PostgreSQL의 unnest() 함수로 keywords 배열을 펼쳐서 집계
    stats_query = (
        select(
            func.unnest(Rating.keywords).label("keyword_code"),
            func.count().label("count_value"),
        )
        .where(
            and_(
                Rating.reviewee_id == user_id,
                Rating.keywords.isnot(None),
                func.array_length(Rating.keywords, 1) > 0,
            )
        )
        .group_by(func.unnest(Rating.keywords))
        .order_by(func.count().desc())
    )

    stats_result = await session.execute(stats_query)
    stats_rows = stats_result.all()

    # keyword_master에서 name_kr 가져오기
    keyword_codes = [row.keyword_code for row in stats_rows]
    keyword_names_query = select(RatingKeywordMaster).where(
        RatingKeywordMaster.code.in_(keyword_codes)
    )
    keyword_names_result = await session.execute(keyword_names_query)
    keyword_masters = keyword_names_result.scalars().all()

    # keyword_code -> name_kr 매핑 생성
    keyword_name_map = {km.code: km.name_kr for km in keyword_masters}

    # UserKeywordStatsResponse로 변환
    stats_data = [
        UserKeywordStatsResponse(
            keyword_code=row.keyword_code,
            name_kr=keyword_name_map.get(row.keyword_code, row.keyword_code),
            count=row.count_value,
        )
        for row in stats_rows
    ]

    return UserKeywordStatsListResponse(items=stats_data)


@router.get(
    "/users/{user_id}/stats/ratings",
    response_model=UserRatingStatsResponse,
    description="사용자 별점 통계 조회",
)
async def get_user_rating_stats(
    user_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> UserRatingStatsResponse:
    """사용자의 별점 통계를 조회합니다."""

    # 사용자 존재 확인
    user_query = select(User).where(User.id == user_id)
    user_result = await session.execute(user_query)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )

    # Rating 테이블에서 별점 통계 집계
    stats_query = select(
        func.avg(Rating.stars).label("average_rating"),
        func.count(Rating.stars).label("total_ratings"),
    ).where(Rating.reviewee_id == user_id)

    stats_result = await session.execute(stats_query)
    stats_row = stats_result.first()

    if stats_row:
        average_rating = (
            float(stats_row.average_rating) if stats_row.average_rating else 0.0
        )
        total_ratings = stats_row.total_ratings or 0
    else:
        average_rating = 0.0
        total_ratings = 0

    # 별점별 분포 조회 (1점~5점)
    distribution_query = (
        select(
            Rating.stars,
            func.count(Rating.stars).label("count_value"),
        )
        .where(Rating.reviewee_id == user_id)
        .group_by(Rating.stars)
        .order_by(Rating.stars)
    )

    distribution_result = await session.execute(distribution_query)
    distribution_rows = distribution_result.all()

    # 분포 데이터 준비
    distribution_data = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}

    # 실제 데이터로 업데이트
    for row in distribution_rows:
        stars = str(int(row.stars))
        count = int(row.count_value)
        distribution_data[stars] = count

    return UserRatingStatsResponse(
        user_id=user_id,
        average_rating=round(average_rating, 2),
        total_ratings=total_ratings,
        rating_distribution=RatingDistribution(**distribution_data),
    )
