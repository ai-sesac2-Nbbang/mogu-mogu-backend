from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import api_messages, deps
from app.core.database_session import get_async_session
from app.enums import ParticipationStatusEnum, PostStatusEnum
from app.models import MoguPost, Participation, User
from app.schemas.requests import ParticipationStatusUpdateRequest
from app.schemas.responses import (
    ParticipationListResponse,
    ParticipationMessageResponse,
    ParticipationResponse,
    ParticipationWithUserResponse,
)

router = APIRouter()


@router.post(
    "/{post_id}/participate",
    response_model=ParticipationMessageResponse,
    description="참여 요청",
)
async def participate_mogu_post(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ParticipationMessageResponse:
    """모구 게시물에 참여 요청합니다."""

    # 게시물 조회
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # 모집 가능한 상태인지 확인
    if mogu_post.status != PostStatusEnum.RECRUITING:
        raise HTTPException(
            status_code=400,
            detail="현재 모집 중이 아닙니다.",
        )

    # 작성자는 참여할 수 없음
    if mogu_post.user_id == current_user.id:
        raise HTTPException(
            status_code=400,
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
                status_code=400,
                detail="이미 참여 신청하거나 승인된 상태입니다.",
            )
        elif existing_participation.status == ParticipationStatusEnum.REJECTED:
            raise HTTPException(
                status_code=400,
                detail="거절된 참여 신청입니다.",
            )

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

    return ParticipationMessageResponse(
        message="참여 요청이 완료되었습니다.",
        participation=ParticipationResponse(
            user_id=participation.user_id,
            mogu_post_id=participation.mogu_post_id,
            status=participation.status,
            applied_at=participation.applied_at,
            decided_at=participation.decided_at,
        ),
    )


@router.delete(
    "/{post_id}/participate",
    response_model=ParticipationMessageResponse,
    description="참여 취소",
)
async def cancel_participation(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ParticipationMessageResponse:
    """모구 게시물 참여를 취소합니다."""

    # 참여 신청 조회
    query = select(Participation).where(
        and_(
            Participation.mogu_post_id == post_id,
            Participation.user_id == current_user.id,
        )
    )
    result = await session.execute(query)
    participation = result.scalar_one_or_none()

    if not participation:
        raise HTTPException(
            status_code=404,
            detail="참여 신청을 찾을 수 없습니다.",
        )

    # 취소 가능한 상태인지 확인
    if participation.status not in [
        ParticipationStatusEnum.APPLIED,
        ParticipationStatusEnum.ACCEPTED,
    ]:
        raise HTTPException(
            status_code=400,
            detail="취소할 수 없는 상태입니다.",
        )

    # 참여 취소
    participation.status = ParticipationStatusEnum.CANCELED
    participation.decided_at = datetime.utcnow()

    await session.commit()

    return ParticipationMessageResponse(
        message="참여가 취소되었습니다.",
    )


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
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # 모구장 권한 확인
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
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

    return ParticipationListResponse(participants=participants_data)


@router.patch(
    "/{post_id}/participants/{user_id}",
    response_model=ParticipationMessageResponse,
    description="참여 승인/거부 (모구장용)",
)
async def update_participation_status(
    post_id: str,
    user_id: str,
    data: ParticipationStatusUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ParticipationMessageResponse:
    """참여 요청을 승인하거나 거부합니다 (모구장만)."""

    # 게시물 조회
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # 모구장 권한 확인
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="모구장만 참여 요청을 승인/거부할 수 있습니다.",
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
            status_code=404,
            detail="참여 신청을 찾을 수 없습니다.",
        )

    # 승인/거부 가능한 상태인지 확인
    if participation.status != ParticipationStatusEnum.APPLIED:
        raise HTTPException(
            status_code=400,
            detail="승인/거부할 수 없는 상태입니다.",
        )

    # 상태 업데이트
    if data.status == "accepted":
        participation.status = ParticipationStatusEnum.ACCEPTED
        message = "참여 요청이 승인되었습니다."
    elif data.status == "rejected":
        participation.status = ParticipationStatusEnum.REJECTED
        message = "참여 요청이 거부되었습니다."
    else:
        raise HTTPException(
            status_code=400,
            detail="올바르지 않은 상태입니다. 'accepted' 또는 'rejected'를 입력하세요.",
        )

    participation.decided_at = datetime.utcnow()
    await session.commit()

    return ParticipationMessageResponse(
        message=message,
        participation=ParticipationResponse(
            user_id=participation.user_id,
            mogu_post_id=participation.mogu_post_id,
            status=participation.status,
            applied_at=participation.applied_at,
            decided_at=participation.decided_at,
        ),
    )
