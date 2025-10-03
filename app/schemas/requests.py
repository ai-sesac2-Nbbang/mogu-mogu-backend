from datetime import date

from pydantic import BaseModel, EmailStr, field_validator

# 상수
WISH_TIMES_LENGTH = 24


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
    wish_times: list[int] | None = None  # 24시간 배열 (0 또는 1)

    @field_validator("wish_times")
    @classmethod
    def validate_wish_times(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v

        # 24개 요소인지 확인
        if len(v) != WISH_TIMES_LENGTH:
            raise ValueError(
                f"wish_times는 정확히 {WISH_TIMES_LENGTH}개 요소를 가져야 합니다."
            )

        # 각 요소가 0 또는 1인지 확인
        for i, hour in enumerate(v):
            if hour not in [0, 1]:
                raise ValueError(
                    f"wish_times[{i}]는 0 또는 1이어야 합니다. 현재 값: {hour}"
                )

        return v


class WishSpotCreateRequest(BaseRequest):
    """관심 장소 추가"""

    label: str  # "집", "회사" 등
    latitude: float  # 위도
    longitude: float  # 경도
