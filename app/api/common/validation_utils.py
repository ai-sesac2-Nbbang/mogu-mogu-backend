"""
검증 관련 공통 유틸리티 함수들입니다.
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import PostStatusEnum
from app.models import MoguPost


async def _check_qa_activity_allowed(
    mogu_post: MoguPost,
    session: AsyncSession,
) -> None:
    """Q&A 활동이 허용되는 상태인지 확인합니다."""
    if mogu_post.status in [
        PostStatusEnum.DRAFT.value,
        PostStatusEnum.CANCELED.value,
        PostStatusEnum.COMPLETED.value,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 Q&A 활동을 할 수 없는 상태입니다.",
        )
