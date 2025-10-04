from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.api.common import _get_mogu_post
from app.core.database_session import get_async_session
from app.enums import ParticipationStatusEnum, PostStatusEnum
from app.models import Participation, User
from app.schemas.requests import ParticipationStatusUpdateRequest
from app.schemas.responses import (
    ParticipationListResponse,
    ParticipationResponse,
    ParticipationWithUserResponse,
)

router = APIRouter()


# 공통 헬퍼 함수들


async def _get_participation(
    post_id: str, user_id: str, session: AsyncSession
) -> Participation:
    """사용자의 참여 정보를 조회합니다."""
    query = select(Participation).where(
        and_(
            Participation.mogu_post_id == post_id,
            Participation.user_id == user_id,
        )
    )
    result = await session.execute(query)
    participation = result.scalar_one_or_none()

    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="참여 신청을 찾을 수 없습니다.",
        )

    return participation


@router.post(
    "/{post_id}/participate",
    response_model=ParticipationResponse,
    status_code=status.HTTP_201_CREATED,
    description="참여 요청",
)
async def participate_mogu_post(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ParticipationResponse:
    """모구 게시물에 참여 요청합니다."""

    # 게시물 조회
    mogu_post = await _get_mogu_post(post_id, session)

    # 모집 가능한 상태인지 확인
    if mogu_post.status != PostStatusEnum.RECRUITING.value:
        status_messages = {
            "locked": "모집이 마감되었습니다.",
            "purchasing": "이미 구매 진행 중입니다.",
            "distributing": "이미 분배 진행 중입니다.",
            "completed": "이미 완료된 모구입니다.",
            "canceled": "취소된 모구입니다.",
        }
        message = status_messages.get(
            mogu_post.status, "현재 참여할 수 없는 상태입니다."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    # 작성자는 참여할 수 없음
    if mogu_post.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="게시물 작성자는 참여할 수 없습니다.",
        )

    # 이미 참여 신청했는지 확인
    existing_participation_query = select(Participation).where(
        and_(
            Participation.mogu_post_id == post_id,
            Participation.user_id == current_user.id,
        )
    )
    existing_result = await session.execute(existing_participation_query)
    existing_participation = existing_result.scalar_one_or_none()

    if existing_participation:
        if existing_participation.status in [
            ParticipationStatusEnum.APPLIED,
            ParticipationStatusEnum.ACCEPTED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 참여 신청하거나 승인된 상태입니다.",
            )
        elif existing_participation.status in [
            ParticipationStatusEnum.REJECTED,
            ParticipationStatusEnum.CANCELED,
        ]:
            # 재신청 허용: 기존 기록을 업데이트
            existing_participation.status = ParticipationStatusEnum.APPLIED
            existing_participation.applied_at = datetime.utcnow()
            existing_participation.decided_at = None

            await session.commit()
            await session.refresh(existing_participation)

            return ParticipationResponse.from_participation(existing_participation)

    # 새로운 참여 요청 생성
    participation = Participation(
        mogu_post_id=post_id,
        user_id=current_user.id,
        status=ParticipationStatusEnum.APPLIED,
        applied_at=datetime.utcnow(),
    )

    session.add(participation)
    await session.commit()
    await session.refresh(participation)

    return ParticipationResponse.from_participation(participation)


@router.delete(
    "/{post_id}/participate",
    status_code=status.HTTP_204_NO_CONTENT,
    description="참여 취소",
)
async def cancel_participation(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """모구 게시물 참여를 취소합니다."""

    # 모구 게시물 조회
    mogu_post = await _get_mogu_post(post_id, session)

    # 참여 신청 조회
    participation = await _get_participation(post_id, current_user.id, session)

    # 취소 가능한 상태인지 확인
    if participation.status not in [
        ParticipationStatusEnum.APPLIED,
        ParticipationStatusEnum.ACCEPTED,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="취소할 수 없는 상태입니다.",
        )

    # 참여 취소
    # ACCEPTED 상태였다면 joined_count 감소
    if participation.status == ParticipationStatusEnum.ACCEPTED:
        mogu_post.joined_count -= 1

    participation.status = ParticipationStatusEnum.CANCELED
    participation.decided_at = datetime.utcnow()

    await session.commit()


@router.get(
    "/{post_id}/participants",
    response_model=ParticipationListResponse,
    description="참여자 목록 조회 (모구장용)",
)
async def get_participants(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ParticipationListResponse:
    """모구 게시물의 참여자 목록을 조회합니다 (모구장만)."""

    # 게시물 조회
    mogu_post = await _get_mogu_post(post_id, session)

    # 모구장 권한 확인
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="모구장만 참여자 목록을 조회할 수 있습니다.",
        )

    # 참여자 목록 조회
    participants_query = (
        select(Participation)
        .options(selectinload(Participation.user))
        .where(Participation.mogu_post_id == post_id)
        .order_by(Participation.applied_at)
    )

    participants_result = await session.execute(participants_query)
    participants = participants_result.scalars().all()

    participants_data = []
    for participation in participants:
        participants_data.append(
            ParticipationWithUserResponse(
                user_id=participation.user_id,
                status=participation.status,
                applied_at=participation.applied_at,
                decided_at=participation.decided_at,
                user={
                    "id": participation.user.id,
                    "nickname": participation.user.nickname,
                    "profile_image_url": participation.user.profile_image_url,
                },
            )
        )

    return ParticipationListResponse(items=participants_data)


@router.patch(
    "/{post_id}/participants/{user_id}",
    response_model=ParticipationResponse,
    description="참여 상태 관리 (모구장용)",
)
async def update_participation_status(
    post_id: str,
    user_id: str,
    data: ParticipationStatusUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ParticipationResponse:
    """참여 상태를 관리합니다 (모구장만)."""

    # 게시물 조회
    mogu_post = await _get_mogu_post(post_id, session)

    # 모구장 권한 확인
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="모구장만 참여 요청을 승인/거부할 수 있습니다.",
        )

    # 참여 상태 관리 가능한 상태인지 확인
    if mogu_post.status not in [
        PostStatusEnum.RECRUITING,
        PostStatusEnum.LOCKED,
        PostStatusEnum.PURCHASING,
        PostStatusEnum.DISTRIBUTING,
        PostStatusEnum.COMPLETED,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 참여 상태를 관리할 수 없는 상태입니다.",
        )

    # 참여 신청 조회
    participation_query = select(Participation).where(
        and_(
            Participation.mogu_post_id == post_id,
            Participation.user_id == user_id,
        )
    )
    participation_result = await session.execute(participation_query)
    participation = participation_result.scalar_one_or_none()

    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="참여 신청을 찾을 수 없습니다.",
        )

    # 상태 변경 가능한 상태인지 확인
    allowed_status_changes = {
        "accepted": [ParticipationStatusEnum.APPLIED],
        "rejected": [ParticipationStatusEnum.APPLIED],
        "no_show": [ParticipationStatusEnum.FULFILLED],
        "fulfilled": [
            ParticipationStatusEnum.ACCEPTED,
            ParticipationStatusEnum.NO_SHOW,
        ],
    }

    if participation.status not in allowed_status_changes.get(data.status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"현재 상태({participation.status})에서는 '{data.status}'로 변경할 수 없습니다.",
        )

    # 상태 업데이트
    if data.status == "accepted":
        # 참여자 수 제한 검증
        if mogu_post.target_count and mogu_post.joined_count >= mogu_post.target_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="모구 인원이 이미 가득 찼습니다.",
            )

        participation.status = ParticipationStatusEnum.ACCEPTED

        # 모구 게시물의 joined_count 증가
        mogu_post.joined_count += 1

    elif data.status == "rejected":
        participation.status = ParticipationStatusEnum.REJECTED

    elif data.status == "no_show":
        participation.status = ParticipationStatusEnum.NO_SHOW

    elif data.status == "fulfilled":
        participation.status = ParticipationStatusEnum.FULFILLED
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="올바르지 않은 상태입니다. 'accepted', 'rejected', 'no_show', 'fulfilled' 중 하나를 입력하세요.",
        )

    participation.decided_at = datetime.utcnow()
    await session.commit()

    return ParticipationResponse.from_participation(participation)
