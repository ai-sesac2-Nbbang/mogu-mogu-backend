from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccessTokenResponse(BaseResponse):
    token_type: str = "Bearer"
    access_token: str
    expires_at: int
    refresh_token: str
    refresh_token_expires_at: int


class UserResponse(BaseResponse):
    user_id: str
    email: EmailStr

    # 카카오 로그인 정보
    kakao_id: int | None = None
    provider: str | None = None

    # 기본 정보
    nickname: str | None = None
    profile_image_url: str | None = None

    # 온보딩 정보
    name: str | None = None
    phone_number: str | None = None
    birth_date: date | None = None
    gender: str | None = None

    # 관심사
    interested_categories: list[str] | None = None
    household_size: str | None = None
    wish_markets: list[str] | None = None
    wish_times: list[int] | None = None

    # 상태
    status: str
    reported_count: int

    # 타임스탬프
    onboarded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WishSpotResponse(BaseResponse):
    id: int
    label: str
    latitude: float
    longitude: float
    created_at: datetime


class KakaoUserResponse(BaseResponse):
    kakao_id: int
    nickname: str | None = None
    profile_image: str | None = None
    email: str | None = None
    connected_at: str


# 찜하기 관련 응답 스키마
class MoguFavoriteResponse(BaseResponse):
    user_id: str
    mogu_post_id: str
    created_at: datetime


class MoguFavoriteStatusResponse(BaseResponse):
    is_favorited: bool
    favorited_at: datetime | None = None


# 키워드 관련 응답 스키마
class RatingKeywordMasterResponse(BaseResponse):
    id: int
    code: str
    name_kr: str
    type: str  # positive 또는 negative
    created_at: datetime


class UserKeywordStatsResponse(BaseResponse):
    user_id: str
    keyword_code: str
    count: int
    last_updated: datetime


class UserKeywordStatsSummaryResponse(BaseResponse):
    user_id: str
    positive_keywords: list[dict[str, Any]]
    negative_keywords: list[dict[str, Any]]
    total_positive_count: int
    total_negative_count: int
    last_updated: datetime


# 모구 게시물 관련 Response 스키마
class MoguSpotResponse(BaseResponse):
    latitude: float
    longitude: float


class MoguPostImageResponse(BaseResponse):
    id: str
    image_url: str
    sort_order: int
    is_thumbnail: bool


class MoguPostUserResponse(BaseResponse):
    id: str
    nickname: str
    profile_image_url: str | None = None


class MoguPostParticipationResponse(BaseResponse):
    status: str
    joined_at: datetime | None = None


class MoguPostResponse(BaseResponse):
    id: str
    user_id: str
    title: str
    description: str | None = None
    price: int
    category: str
    mogu_market: str
    mogu_spot: dict[str, float]
    mogu_datetime: datetime
    status: str
    target_count: int | None = None
    joined_count: int
    created_at: datetime
    images: list[dict[str, Any]] | None = None
    user: dict[str, str | None]
    my_participation: dict[str, Any] | None = None
    is_favorited: bool | None = None


class MoguPostListResponse(BaseResponse):
    id: str
    user_id: str
    title: str
    description: str | None = None
    price: int
    category: str
    mogu_market: str
    mogu_spot: dict[str, float]
    mogu_datetime: datetime
    status: str
    target_count: int | None = None
    joined_count: int
    created_at: datetime
    images: list[dict[str, Any]] | None = None
    user: dict[str, str | None]
    my_participation: dict[str, Any] | None = None
    is_favorited: bool | None = None


class MoguPostListPaginatedResponse(BaseResponse):
    items: list[MoguPostListResponse]
    total: int
    page: int
    size: int
    has_next: bool
