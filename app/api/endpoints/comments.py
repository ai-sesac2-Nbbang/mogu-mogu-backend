"""댓글 관리 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.common import _check_comment_activity_allowed, _get_mogu_post
from app.core.database_session import get_async_session
from app.models import MoguComment, User
from app.schemas.requests import CommentCreateRequest
from app.schemas.responses import CommentResponse

router = APIRouter()


async def _get_comment(
    post_id: str,
    comment_id: str,
    session: AsyncSession,
) -> MoguComment:
    """댓글을 조회합니다."""
    comment_query = select(MoguComment).where(
        and_(
            MoguComment.id == comment_id,
            MoguComment.mogu_post_id == post_id,
        )
    )
    comment_result = await session.execute(comment_query)
    comment = comment_result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="댓글을 찾을 수 없습니다.",
        )

    return comment


@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    description="댓글 작성",
)
async def create_comment(
    post_id: str,
    data: CommentCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CommentResponse:
    """모구 게시물에 댓글을 작성합니다."""

    # 게시물 조회 및 상태 확인
    mogu_post = await _get_mogu_post(post_id, session)
    await _check_comment_activity_allowed(mogu_post, session)

    # 댓글 생성
    comment = MoguComment(
        mogu_post_id=post_id,
        user_id=current_user.id,
        content=data.content,
    )

    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    # 사용자 정보 로드
    await session.refresh(comment, ["user"])

    return CommentResponse(
        id=comment.id,
        user_id=comment.user_id,
        content=comment.content,
        created_at=comment.created_at,
        user={
            "id": comment.user.id,
            "nickname": comment.user.nickname,
            "profile_image_path": comment.user.profile_image_path,
        },
    )


@router.delete(
    "/{post_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="댓글 삭제",
)
async def delete_comment(
    post_id: str,
    comment_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """댓글을 삭제합니다 (댓글 작성자만 가능)."""

    # 댓글 조회
    comment = await _get_comment(post_id, comment_id, session)

    # 댓글 작성자 권한 확인
    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="댓글 작성자만 삭제할 수 있습니다.",
        )

    # 댓글 삭제
    await session.delete(comment)
    await session.commit()
