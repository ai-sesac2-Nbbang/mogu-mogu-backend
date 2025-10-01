from datetime import date, datetime

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

    # 상태
    status: str
    reported_count: int

    # 타임스탬프
    onboarded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KakaoUserResponse(BaseResponse):
    kakao_id: int
    nickname: str | None = None
    profile_image: str | None = None
    email: str | None = None
    connected_at: str
