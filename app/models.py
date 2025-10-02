# SQL Alchemy models declaration.
# https://docs.sqlalchemy.org/en/20/orm/quickstart.html#declare-models
# mapped_column syntax from SQLAlchemy 2.0.

# https://alembic.sqlalchemy.org/en/latest/tutorial.html
# Note, it is used by alembic migrations logic, see `alembic/env.py`

# Alembic shortcuts:
# # create migration
# alembic revision --autogenerate -m "migration_name"

# # apply all migrations
# alembic upgrade head


import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.enums import (
    CategoryEnum,
    GenderEnum,
    HouseholdSizeEnum,
    MarketEnum,
    ParticipationStatusEnum,
    PostStatusEnum,
    UserStatusEnum,
)


class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserWishSpot(Base):
    """사용자 관심 장소 (최대 2개)"""

    __tablename__ = "user_wish_spot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)  # "집", "회사" 등
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )  # WGS84 좌표계 (경도, 위도)

    user: Mapped["User"] = relationship(back_populates="wish_spots")


class User(Base):
    """서비스 사용자"""

    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda _: str(uuid.uuid4())
    )

    # 카카오 로그인 정보
    kakao_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="kakao")

    # 기본 정보 (카카오에서 가져옴)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 온보딩 필수 정보 (추가 입력 필요)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(
        SQLEnum(
            GenderEnum,
            name="gender_enum",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )

    # 관심사
    interested_categories: Mapped[list[str] | None] = mapped_column(
        ARRAY(
            SQLEnum(
                CategoryEnum,
                name="category_enum",
                create_type=True,
                values_callable=lambda x: [e.value for e in x],
            )
        ),
        nullable=True,
    )
    household_size: Mapped[str | None] = mapped_column(
        SQLEnum(
            HouseholdSizeEnum,
            name="household_size_enum",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    wish_markets: Mapped[list[str] | None] = mapped_column(
        ARRAY(
            SQLEnum(
                MarketEnum,
                name="market_enum",
                create_type=True,
                values_callable=lambda x: [e.value for e in x],
            )
        ),
        nullable=True,
    )

    # 사용자 상태
    status: Mapped[str] = mapped_column(
        SQLEnum(
            UserStatusEnum,
            name="user_status_enum",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=UserStatusEnum.PENDING_ONBOARDING.value,
    )

    # 신고/관리
    reported_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # 온보딩 완료 시간
    onboarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 업데이트 시간
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 관계
    wish_spots: Mapped[list["UserWishSpot"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")
    mogu_posts: Mapped[list["MoguPost"]] = relationship(back_populates="user")
    questions_asked: Mapped[list["QuestionAnswer"]] = relationship(
        foreign_keys="QuestionAnswer.questioner_id", back_populates="questioner"
    )
    answers_given: Mapped[list["QuestionAnswer"]] = relationship(
        foreign_keys="QuestionAnswer.answerer_id", back_populates="answerer"
    )
    participations: Mapped[list["Participation"]] = relationship(back_populates="user")
    ratings_given: Mapped[list["Rating"]] = relationship(
        foreign_keys="Rating.reviewer_id", back_populates="reviewer"
    )
    ratings_received: Mapped[list["Rating"]] = relationship(
        foreign_keys="Rating.reviewee_id", back_populates="reviewee"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    refresh_token: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True, index=True
    )
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exp: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"),
    )
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class MoguPost(Base):
    """모구 게시물"""

    __tablename__ = "mogu_post"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda _: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category: Mapped[str] = mapped_column(
        SQLEnum(
            CategoryEnum,
            name="category_enum",
            create_type=False,  # 이미 생성됨
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    mogu_market: Mapped[str] = mapped_column(
        SQLEnum(
            MarketEnum,
            name="market_enum",
            create_type=False,  # 이미 생성됨
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    mogu_spot: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )

    mogu_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        SQLEnum(
            PostStatusEnum,
            name="post_status_enum",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PostStatusEnum.RECRUITING.value,
    )
    target_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    joined_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # 관계
    user: Mapped["User"] = relationship(back_populates="mogu_posts")
    images: Mapped[list["MoguPostImage"]] = relationship(
        back_populates="mogu_post", cascade="all, delete-orphan"
    )
    questions_answers: Mapped[list["QuestionAnswer"]] = relationship(
        back_populates="mogu_post", cascade="all, delete-orphan"
    )
    participations: Mapped[list["Participation"]] = relationship(
        back_populates="mogu_post", cascade="all, delete-orphan"
    )
    ratings: Mapped[list["Rating"]] = relationship(
        back_populates="mogu_post", cascade="all, delete-orphan"
    )


class MoguPostImage(Base):
    """모구 게시물 이미지"""

    __tablename__ = "mogu_post_image"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda _: str(uuid.uuid4())
    )
    mogu_post_id: Mapped[str] = mapped_column(
        ForeignKey("mogu_post.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    is_thumbnail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    mogu_post: Mapped["MoguPost"] = relationship(back_populates="images")


class QuestionAnswer(Base):
    """Q&A (비공개: 작성자/모구장만 열람)"""

    __tablename__ = "question_answer"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda _: str(uuid.uuid4())
    )
    mogu_post_id: Mapped[str] = mapped_column(
        ForeignKey("mogu_post.id", ondelete="CASCADE"), nullable=False, index=True
    )

    questioner_id: Mapped[str] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)

    answerer_id: Mapped[str | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    question_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    answer_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    mogu_post: Mapped["MoguPost"] = relationship(back_populates="questions_answers")
    questioner: Mapped["User"] = relationship(
        foreign_keys=[questioner_id], back_populates="questions_asked"
    )
    answerer: Mapped["User | None"] = relationship(
        foreign_keys=[answerer_id], back_populates="answers_given"
    )


class Participation(Base):
    """포스트 참여"""

    __tablename__ = "participation"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    mogu_post_id: Mapped[str] = mapped_column(
        ForeignKey("mogu_post.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(
        SQLEnum(
            ParticipationStatusEnum,
            name="participation_status_enum",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ParticipationStatusEnum.APPLIED.value,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="participations")
    mogu_post: Mapped["MoguPost"] = relationship(back_populates="participations")


class Rating(Base):
    """평가 (모구 완료 후)"""

    __tablename__ = "rating"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda _: str(uuid.uuid4())
    )
    mogu_post_id: Mapped[str] = mapped_column(
        ForeignKey("mogu_post.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewee_id: Mapped[str] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stars: Mapped[int] = mapped_column(BigInteger, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    mogu_post: Mapped["MoguPost"] = relationship(back_populates="ratings")
    reviewer: Mapped["User"] = relationship(
        foreign_keys=[reviewer_id], back_populates="ratings_given"
    )
    reviewee: Mapped["User"] = relationship(
        foreign_keys=[reviewee_id], back_populates="ratings_received"
    )
