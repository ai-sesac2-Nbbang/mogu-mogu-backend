"""
검증 관련 공통 유틸리티 함수들입니다.
"""

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import PostStatusEnum
from app.models import MoguPost, Participation, User


async def _check_comment_activity_allowed(
    mogu_post: MoguPost,
    session: AsyncSession,
) -> None:
    """댓글 활동이 허용되는 상태인지 확인합니다."""
    if mogu_post.status in [
        PostStatusEnum.DRAFT.value,
        PostStatusEnum.CANCELED.value,
        PostStatusEnum.COMPLETED.value,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 댓글 활동을 할 수 없는 상태입니다.",
        )


async def _check_user_participation_status(
    mogu_post: MoguPost, user_id: str, session: AsyncSession
) -> tuple[bool, bool, Participation | None]:
    """사용자가 모구장인지, 참여자인지 확인하고 참여 정보를 반환합니다."""

    # 모구장인지 확인
    is_mogu_leader = mogu_post.user_id == user_id

    # 모구러인지 확인 (fulfilled 또는 no_show 상태인 참여자)
    participation_query = select(Participation).where(
        and_(
            Participation.mogu_post_id == mogu_post.id,
            Participation.user_id == user_id,
            Participation.status.in_(["fulfilled", "no_show"]),
        )
    )
    participation_result = await session.execute(participation_query)
    participation = participation_result.scalar_one_or_none()
    is_participant = participation is not None

    return is_mogu_leader, is_participant, participation


async def _validate_rating_permissions(
    mogu_post: MoguPost, current_user: User, session: AsyncSession
) -> None:
    """평가 권한을 검증합니다."""

    is_mogu_leader, is_participant, _ = await _check_user_participation_status(
        mogu_post, current_user.id, session
    )

    if not is_mogu_leader and not is_participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="모구장 또는 완료된 참여자만 평가를 작성할 수 있습니다.",
        )
