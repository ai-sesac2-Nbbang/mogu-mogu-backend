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
        SQLEnum(GenderEnum, name="gender_enum", create_type=True), nullable=True
    )

    # 관심사
    interested_categories: Mapped[list[str] | None] = mapped_column(
        ARRAY(SQLEnum(CategoryEnum, name="category_enum", create_type=True)),
        nullable=True,
    )
    household_size: Mapped[str | None] = mapped_column(
        SQLEnum(HouseholdSizeEnum, name="household_size_enum", create_type=True),
        nullable=True,
    )
    wish_markets: Mapped[list[str] | None] = mapped_column(
        ARRAY(SQLEnum(MarketEnum, name="market_enum", create_type=True)),
        nullable=True,
    )

    # 사용자 상태
    status: Mapped[str] = mapped_column(
        SQLEnum(UserStatusEnum, name="user_status_enum", create_type=True),
        nullable=False,
        default=UserStatusEnum.PENDING_ONBOARDING,
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
