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
