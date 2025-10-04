from datetime import date, datetime

from pydantic import BaseModel, EmailStr, field_validator

# 상수
WISH_TIMES_LENGTH = 24
MIN_TARGET_COUNT = 2


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


# 모구 게시물 관련 Request 스키마
class MoguSpotRequest(BaseRequest):
    """모구 장소 정보"""

    latitude: float
    longitude: float


class MoguPostImageRequest(BaseRequest):
    """모구 게시물 이미지 정보"""

    image_url: str
    sort_order: int
    is_thumbnail: bool


class MoguPostCreateRequest(BaseRequest):
    """모구 게시물 생성"""

    title: str
    description: str
    price: int
    category: str  # CategoryEnum 값
    mogu_market: str  # MarketEnum 값
    mogu_spot: MoguSpotRequest
    mogu_datetime: datetime
    target_count: int
    images: list[MoguPostImageRequest] | None = None

    @field_validator("target_count")
    @classmethod
    def validate_target_count(cls, v: int) -> int:
        if v < MIN_TARGET_COUNT:
            raise ValueError(f"target_count는 {MIN_TARGET_COUNT} 이상이어야 합니다.")
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("price는 0보다 커야 합니다.")
        return v


class MoguPostUpdateRequest(BaseRequest):
    """모구 게시물 수정"""

    title: str | None = None
    description: str | None = None
    price: int | None = None
    category: str | None = None
    mogu_market: str | None = None
    mogu_spot: MoguSpotRequest | None = None
    mogu_datetime: datetime | None = None
    target_count: int | None = None
    status: str | None = None  # PostStatusEnum 값
    images: list[MoguPostImageRequest] | None = None

    @field_validator("target_count")
    @classmethod
    def validate_target_count(cls, v: int | None) -> int | None:
        if v is not None and v < MIN_TARGET_COUNT:
            raise ValueError(f"target_count는 {MIN_TARGET_COUNT} 이상이어야 합니다.")
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("price는 0보다 커야 합니다.")
        return v


class MoguPostListQueryParams(BaseRequest):
    """모구 게시물 목록 조회 쿼리 파라미터"""

    page: int = 1
    size: int = 20
    sort: str = "ai_recommended"
    category: str | None = None
    mogu_market: str | None = None
    status: str | None = "recruiting"  # 기본값은 recruiting, None이면 모든 상태 조회
    latitude: float  # 필수 파라미터로 변경
    longitude: float  # 필수 파라미터로 변경
    radius: float = 3.0


# 참여 관련 Request 스키마
class ParticipationStatusUpdateRequest(BaseRequest):
    """참여 상태 업데이트 (승인/거부/노쇼/완료)"""

    status: str  # "accepted", "rejected", "no_show", "fulfilled"
