"""
게시물 관련 공통 유틸리티 함수들입니다.
"""

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import api_messages
from app.enums import PostStatusEnum
from app.models import MoguPost, User


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
