from datetime import date

from pydantic import BaseModel, EmailStr


class BaseRequest(BaseModel):
    # may define additional fields or config shared across requests
    pass


class RefreshTokenRequest(BaseRequest):
    refresh_token: str


class UserUpdatePasswordRequest(BaseRequest):
    password: str


class UserCreateRequest(BaseRequest):
    email: EmailStr
    password: str


class KakaoLoginRequest(BaseRequest):
    code: str
    state: str | None = None


class UserUpdateRequest(BaseRequest):
    """사용자 정보 업데이트 (온보딩 포함)"""

    # 기본 정보
    nickname: str | None = None
    profile_image_url: str | None = None

    # 온보딩 필수 정보
    name: str | None = None
    phone_number: str | None = None
    birth_date: date | None = None
    gender: str | None = None  # "male" | "female" | "other"

    # 관심사
    interested_categories: list[str] | None = None  # CategoryEnum 값들
    household_size: str | None = None  # HouseholdSizeEnum 값
    wish_markets: list[str] | None = None  # MarketEnum 값들


class WishSpotCreateRequest(BaseRequest):
    """관심 장소 추가"""

    label: str  # "집", "회사" 등
    latitude: float  # 위도
    longitude: float  # 경도
