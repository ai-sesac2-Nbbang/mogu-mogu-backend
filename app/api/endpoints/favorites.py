from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import api_messages, deps
from app.api.common import (
    _build_mogu_post_basic_data,
    _calculate_pagination_info,
    _check_favorite_status,
    _execute_paginated_query,
    _get_mogu_post,
)
from app.core.database_session import get_async_session
from app.enums import PostStatusEnum
from app.models import MoguFavorite, MoguPost, User
from app.schemas.responses import (
    MoguPostFavoritesPaginatedResponse,
    MoguPostListItemResponse,
)

router = APIRouter()


@router.post(
    "/{post_id}/favorites",
    status_code=http_status.HTTP_201_CREATED,
    description="게시물 찜하기",
)
async def add_favorite(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """게시물을 찜합니다."""

    # 게시물 존재 확인
    await _get_mogu_post(post_id, session)

    # 이미 찜했는지 확인
    is_favorited = await _check_favorite_status(post_id, current_user.id, session)
    if is_favorited:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="이미 찜한 게시물입니다.",
        )

    # 찜하기 추가
    favorite = MoguFavorite(
        user_id=current_user.id,
        mogu_post_id=post_id,
    )

    session.add(favorite)
    await session.commit()


@router.delete(
    "/{post_id}/favorites",
    status_code=http_status.HTTP_204_NO_CONTENT,
    description="게시물 찜하기 취소",
)
async def remove_favorite(
    post_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """게시물 찜하기를 취소합니다."""

    # 찜하기 존재 확인
    favorite_query = select(MoguFavorite).where(
        and_(
            MoguFavorite.mogu_post_id == post_id,
            MoguFavorite.user_id == current_user.id,
        )
    )
    favorite_result = await session.execute(favorite_query)
    favorite = favorite_result.scalar_one_or_none()

    if not favorite:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="찜하지 않은 게시물입니다.",
        )

    # 찜하기 삭제
    await session.delete(favorite)
    await session.commit()


@router.get(
    "/my-favorites",
    response_model=MoguPostFavoritesPaginatedResponse,
    description="내가 찜한 게시물 목록",
)
async def get_my_favorites(
    status: str | None = None,
    page: int = 1,
    size: int = 20,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> MoguPostFavoritesPaginatedResponse:
    """내가 찜한 게시물 목록을 조회합니다."""

    # 찜한 게시물 조회를 위한 기본 쿼리
    query = (
        select(MoguPost)
        .join(MoguFavorite, MoguFavorite.mogu_post_id == MoguPost.id)
        .where(MoguFavorite.user_id == current_user.id)
        .options(selectinload(MoguPost.images))
    )

    # 상태 필터 적용
    if status:
        try:
            status_enum = PostStatusEnum(status)
            query = query.where(MoguPost.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=api_messages.INVALID_STATUS_VALUE,
            )

    # 정렬 (최신 찜하기 순)
    query = query.order_by(desc(MoguFavorite.created_at))

    # 페이지네이션 적용된 쿼리 실행
    result, total = await _execute_paginated_query(query, page, size, session)
    posts = result.scalars().all()

    # 응답 데이터 구성
    posts_list = []
    for post in posts:
        # 게시물 기본 데이터 구성
        basic_data = await _build_mogu_post_basic_data(post, session)

        posts_list.append(
            MoguPostListItemResponse(
                id=post.id,
                title=post.title,
                price=post.price,
                category=post.category,
                mogu_market=post.mogu_market,
                mogu_datetime=post.mogu_datetime,
                status=post.status,
                target_count=post.target_count or 0,
                joined_count=post.joined_count,
                created_at=post.created_at,
                thumbnail_image=basic_data["thumbnail_image"],
                favorite_count=basic_data["favorite_count"],
            )
        )

    return MoguPostFavoritesPaginatedResponse(
        items=posts_list,
        pagination=await _calculate_pagination_info(page, size, total),
    )
