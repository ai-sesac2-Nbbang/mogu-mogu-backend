#!/usr/bin/env python3
"""
더미 데이터를 데이터베이스에 삽입하는 스크립트
"""

import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_session import get_async_session
from app.enums import (
    CategoryEnum,
    GenderEnum,
    HouseholdSizeEnum,
    MarketEnum,
    ParticipationStatusEnum,
    PostStatusEnum,
    UserStatusEnum,
)
from app.models import (
    MoguComment,
    MoguFavorite,
    MoguPost,
    Participation,
    Rating,
    User,
    UserWishSpot,
)


async def insert_users(session: AsyncSession, users_data: list[dict[str, Any]]) -> None:
    """사용자 데이터 삽입"""
    print("👥 사용자 데이터 삽입 중...")

    for user_data in users_data:
        # 기존 사용자 확인
        existing_user = await session.execute(
            select(User).where(User.email == user_data["email"])
        )
        if existing_user.scalar_one_or_none():
            continue

        # 사용자 생성
        user = User(
            id=user_data["id"],
            kakao_id=hash(user_data["email"]) % 1000000000,  # 가짜 카카오 ID
            provider="kakao",
            email=user_data["email"],
            nickname=user_data["nickname"],
            name=user_data["nickname"].split("_")[-1],  # 닉네임에서 이름 추출
            gender=GenderEnum(user_data["gender"]),
            birth_date=(
                date.fromisoformat(user_data["birth_date"])
                if isinstance(user_data["birth_date"], str)
                else user_data["birth_date"]
            ),
            household_size=HouseholdSizeEnum(user_data["household_size"]),
            interested_categories=[
                CategoryEnum(cat) for cat in user_data["interested_categories"]
            ],
            wish_markets=[MarketEnum(market) for market in user_data["wish_markets"]],
            wish_times=user_data["wish_times"],
            status=UserStatusEnum(user_data["status"]),
            onboarded_at=datetime.now(),
        )

        session.add(user)

    await session.commit()
    print(f"✅ {len(users_data)}명의 사용자 삽입 완료")


async def insert_wish_spots(
    session: AsyncSession, wish_spots_data: list[dict[str, Any]]
) -> None:
    """위시스팟 데이터 삽입"""
    print("📍 위시스팟 데이터 삽입 중...")

    for wish_spot_data in wish_spots_data:
        # 기존 위시스팟 확인 (user_id와 label로 중복 체크)
        existing_spot = await session.execute(
            select(UserWishSpot).where(
                UserWishSpot.user_id == wish_spot_data["user_id"],
                UserWishSpot.label == wish_spot_data["label"],
            )
        )
        if existing_spot.scalar_one_or_none():
            continue

        # 위시스팟 생성
        lat, lon = wish_spot_data["location"]
        created_at = wish_spot_data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        wish_spot = UserWishSpot(
            user_id=wish_spot_data["user_id"],
            label=wish_spot_data["label"],
            location=f"POINT({lon} {lat})",  # PostGIS POINT 형식
            created_at=created_at,
        )
        session.add(wish_spot)

    await session.commit()
    print(f"✅ {len(wish_spots_data)}개의 위시스팟 삽입 완료")


async def insert_mogu_posts(
    session: AsyncSession, posts_data: list[dict[str, Any]]
) -> None:
    """모구 게시물 데이터 삽입"""
    print("📝 모구 게시물 데이터 삽입 중...")

    for post_data in posts_data:
        # 기존 게시물 확인
        existing_post = await session.execute(
            select(MoguPost).where(MoguPost.id == post_data["id"])
        )
        if existing_post.scalar_one_or_none():
            continue

        # 게시물 생성
        mogu_datetime = post_data["mogu_datetime"]
        if isinstance(mogu_datetime, str):
            mogu_datetime = datetime.fromisoformat(mogu_datetime.replace("Z", "+00:00"))

        created_at = post_data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        post = MoguPost(
            id=post_data["id"],
            user_id=post_data["user_id"],
            title=post_data["title"],
            description=post_data["description"],
            price=post_data["price"],
            labor_fee=post_data["labor_fee"],
            category=CategoryEnum(post_data["category"]),
            mogu_market=MarketEnum(post_data["mogu_market"]),
            mogu_spot=f"POINT({post_data['mogu_spot'][1]} {post_data['mogu_spot'][0]})",  # PostGIS POINT
            mogu_datetime=mogu_datetime,
            status=PostStatusEnum(post_data["status"]),
            target_count=post_data["target_count"],
            joined_count=post_data["joined_count"],
            created_at=created_at,
        )

        session.add(post)

    await session.commit()
    print(f"✅ {len(posts_data)}개의 모구 게시물 삽입 완료")


async def insert_favorites(
    session: AsyncSession, favorites_data: list[dict[str, Any]]
) -> None:
    """찜하기 데이터 삽입"""
    print("❤️ 찜하기 데이터 삽입 중...")

    favorites = []
    for favorite_data in favorites_data:
        # 기존 찜하기 확인
        existing_favorite = await session.execute(
            select(MoguFavorite).where(
                MoguFavorite.user_id == favorite_data["user_id"],
                MoguFavorite.mogu_post_id == favorite_data["mogu_post_id"],
            )
        )
        if existing_favorite.scalar_one_or_none():
            continue

        # 찜하기 생성
        created_at = favorite_data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        favorite = MoguFavorite(
            user_id=favorite_data["user_id"],
            mogu_post_id=favorite_data["mogu_post_id"],
            created_at=created_at,
        )
        favorites.append(favorite)

    # 배치 삽입
    if favorites:
        session.add_all(favorites)
        await session.commit()

    print(f"✅ {len(favorites)}개의 찜하기 삽입 완료")


async def insert_participations(
    session: AsyncSession, participations_data: list[dict[str, Any]]
) -> None:
    """참여 데이터 삽입"""
    print("👥 참여 데이터 삽입 중...")

    participations = []
    for participation_data in participations_data:
        # 기존 참여 확인
        existing_participation = await session.execute(
            select(Participation).where(
                Participation.user_id == participation_data["user_id"],
                Participation.mogu_post_id == participation_data["mogu_post_id"],
            )
        )
        if existing_participation.scalar_one_or_none():
            continue

        # 참여 생성
        applied_at = participation_data["applied_at"]
        if isinstance(applied_at, str):
            applied_at = datetime.fromisoformat(applied_at.replace("Z", "+00:00"))

        decided_at = participation_data.get("decided_at")
        if decided_at and isinstance(decided_at, str):
            decided_at = datetime.fromisoformat(decided_at.replace("Z", "+00:00"))

        participation = Participation(
            user_id=participation_data["user_id"],
            mogu_post_id=participation_data["mogu_post_id"],
            status=ParticipationStatusEnum(participation_data["status"]),
            applied_at=applied_at,
            decided_at=decided_at,
        )
        participations.append(participation)

    # 배치 삽입
    if participations:
        session.add_all(participations)
        await session.commit()

    print(f"✅ {len(participations)}개의 참여 삽입 완료")


async def insert_comments(
    session: AsyncSession, comments_data: list[dict[str, Any]]
) -> None:
    """댓글 데이터 삽입"""
    print("💬 댓글 데이터 삽입 중...")

    comments = []
    for comment_data in comments_data:
        # 기존 댓글 확인
        existing_comment = await session.execute(
            select(MoguComment).where(MoguComment.id == comment_data["id"])
        )
        if existing_comment.scalar_one_or_none():
            continue

        # 댓글 생성
        created_at = comment_data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        comment = MoguComment(
            id=comment_data["id"],
            mogu_post_id=comment_data["mogu_post_id"],
            user_id=comment_data["user_id"],
            content=comment_data["content"],
            created_at=created_at,
        )
        comments.append(comment)

    # 배치 삽입
    if comments:
        session.add_all(comments)
        await session.commit()

    print(f"✅ {len(comments)}개의 댓글 삽입 완료")


async def insert_ratings(
    session: AsyncSession, ratings_data: list[dict[str, Any]]
) -> None:
    """평가 데이터 삽입"""
    print("⭐ 평가 데이터 삽입 중...")

    for rating_data in ratings_data:
        # 기존 평가 확인
        existing_rating = await session.execute(
            select(Rating).where(
                Rating.mogu_post_id == rating_data["mogu_post_id"],
                Rating.reviewer_id == rating_data["reviewer_id"],
            )
        )
        if existing_rating.scalar_one_or_none():
            continue

        # 평가 생성
        created_at = rating_data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        rating = Rating(
            id=rating_data["id"],
            mogu_post_id=rating_data["mogu_post_id"],
            reviewer_id=rating_data["reviewer_id"],
            reviewee_id=rating_data["reviewee_id"],
            stars=rating_data["stars"],
            keywords=rating_data["keywords"],
            created_at=created_at,
        )

        session.add(rating)

    await session.commit()
    print(f"✅ {len(ratings_data)}개의 평가 삽입 완료")


async def main() -> None:
    """메인 실행 함수"""
    print("🚀 더미 데이터 데이터베이스 삽입 시작...")

    # 더미 데이터 로드
    try:
        with open("dummy_data.json", encoding="utf-8") as f:
            dummy_data = json.load(f)
    except FileNotFoundError:
        print("❌ dummy_data.json 파일을 찾을 수 없습니다.")
        print("먼저 generate_dummy_data.py를 실행해주세요.")
        return

    # 데이터베이스 세션 생성
    async with get_async_session() as session:
        try:
            # 1. 사용자 데이터 삽입
            await insert_users(session, dummy_data["users"])

            # 2. 위시스팟 데이터 삽입
            await insert_wish_spots(session, dummy_data["wish_spots"])

            # 3. 모구 게시물 데이터 삽입
            await insert_mogu_posts(session, dummy_data["mogu_posts"])

            # 4. 찜하기 데이터 삽입
            await insert_favorites(session, dummy_data["favorites"])

            # 5. 참여 데이터 삽입
            await insert_participations(session, dummy_data["participations"])

            # 6. 댓글 데이터 삽입
            await insert_comments(session, dummy_data["comments"])

            # 7. 평가 데이터 삽입
            await insert_ratings(session, dummy_data["ratings"])

            print("🎉 모든 더미 데이터 삽입 완료!")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
