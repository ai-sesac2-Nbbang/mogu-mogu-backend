"""
게시물 관련 공통 유틸리티 함수들입니다.
"""

from typing import Any, TypedDict

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import api_messages
from app.enums import PostStatusEnum
from app.models import MoguFavorite, MoguPost, Participation, User
from app.schemas.responses import PaginationInfo, ParticipationInfo


class MoguPostBasicData(TypedDict):
    """게시물 기본 데이터 타입"""

    favorite_count: int
    thumbnail_image: str | None


async def _get_mogu_post(post_id: str, session: AsyncSession) -> MoguPost:
    """모구 게시물을 조회합니다."""
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    return mogu_post


async def _get_mogu_post_with_relations(
    post_id: str, session: AsyncSession
) -> MoguPost:
    """관계 데이터와 함께 모구 게시물을 조회합니다."""
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
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    return mogu_post


async def _check_post_permissions(mogu_post: MoguPost, current_user: User) -> None:
    """게시물 권한을 확인합니다."""
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="모구 게시물 작성자만 접근할 수 있습니다.",
        )


async def _validate_post_status_for_deletion(mogu_post: MoguPost) -> None:
    """게시물 삭제 가능 여부를 확인합니다."""
    if mogu_post.status in [
        PostStatusEnum.PURCHASING,
        PostStatusEnum.DISTRIBUTING,
        PostStatusEnum.COMPLETED,
    ]:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="진행 중인 모구 게시물은 삭제할 수 없습니다.",
        )


async def _get_user_participation_status(
    post_id: str, user_id: str, session: AsyncSession
) -> ParticipationInfo | None:
    """사용자의 참여 상태를 조회합니다."""
    participation_query = select(Participation).where(
        and_(
            Participation.mogu_post_id == post_id,
            Participation.user_id == user_id,
        )
    )
    participation_result = await session.execute(participation_query)
    participation = participation_result.scalar_one_or_none()

    if participation:
        return {
            "status": participation.status,
            "applied_at": participation.applied_at.isoformat(),
            "decided_at": (
                participation.decided_at.isoformat()
                if participation.decided_at
                else None
            ),
        }
    return None


async def _check_favorite_status(
    post_id: str, user_id: str, session: AsyncSession
) -> bool:
    """사용자의 찜하기 상태를 확인합니다."""
    favorite_query = select(MoguFavorite).where(
        and_(
            MoguFavorite.mogu_post_id == post_id,
            MoguFavorite.user_id == user_id,
        )
    )
    favorite_result = await session.execute(favorite_query)
    return favorite_result.scalar_one_or_none() is not None


async def _get_favorite_count(post_id: str, session: AsyncSession) -> int:
    """게시물의 찜하기 개수를 조회합니다."""
    favorite_count_query = (
        select(func.count())
        .select_from(MoguFavorite)
        .where(MoguFavorite.mogu_post_id == post_id)
    )
    favorite_count_result = await session.execute(favorite_count_query)
    return favorite_count_result.scalar() or 0


def _extract_thumbnail_image(post: MoguPost) -> str | None:
    """게시물에서 썸네일 이미지 URL을 추출합니다."""
    if not post.images:
        return None

    # 썸네일 이미지 찾기
    thumbnail_img = next((img for img in post.images if img.is_thumbnail), None)
    if thumbnail_img:
        return thumbnail_img.image_path
    else:
        # 썸네일이 없으면 첫 번째 이미지 사용
        return post.images[0].image_path


async def _calculate_pagination_info(
    page: int, size: int, total: int
) -> PaginationInfo:
    """페이지네이션 정보를 계산합니다."""
    return {
        "page": page,
        "limit": size,
        "total": total,
        "total_pages": (total + size - 1) // size,
    }


async def _execute_paginated_query(
    query: Any, page: int, size: int, session: AsyncSession
) -> tuple[Any, int]:
    """페이지네이션이 적용된 쿼리를 실행하고 결과와 총 개수를 반환합니다."""
    # 전체 개수 조회
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # 페이지네이션 적용
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    # 쿼리 실행
    result = await session.execute(query)
    return result, total


async def _build_mogu_post_basic_data(
    post: MoguPost, session: AsyncSession
) -> MoguPostBasicData:
    """게시물의 기본 데이터(favorite_count, thumbnail_image)를 구성합니다."""
    favorite_count = await _get_favorite_count(post.id, session)
    thumbnail_image = _extract_thumbnail_image(post)

    return {
        "favorite_count": favorite_count,
        "thumbnail_image": thumbnail_image,
    }
