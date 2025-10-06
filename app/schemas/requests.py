from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.types import (
    CategoryLiteral,
    GenderLiteral,
    HouseholdSizeLiteral,
    MarketLiteral,
    ParticipationStatusLiteral,
    PostStatusLiteral,
    RatingKeywordCodeLiteral,
    SortLiteral,
)

# 상수
WISH_TIMES_LENGTH = 24
MIN_TARGET_COUNT = 1


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
    gender: GenderLiteral | None = None

    # 관심사
    interested_categories: list[CategoryLiteral] | None = None
    household_size: HouseholdSizeLiteral | None = None
    wish_markets: list[MarketLiteral] | None = None
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
    labor_fee: int = 0
    category: CategoryLiteral
    mogu_market: MarketLiteral
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
    labor_fee: int | None = None
    category: CategoryLiteral | None = None
    mogu_market: MarketLiteral | None = None
    mogu_spot: MoguSpotRequest | None = None
    mogu_datetime: datetime | None = None
    target_count: int | None = None
    status: PostStatusLiteral | None = None
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
    sort: SortLiteral = "ai_recommended"
    category: CategoryLiteral | None = None
    mogu_market: MarketLiteral | None = None
    status: PostStatusLiteral | None = (
        "recruiting"  # 기본값은 recruiting, None이면 모든 상태 조회
    )
    latitude: float  # 필수 파라미터로 변경
    longitude: float  # 필수 파라미터로 변경
    radius: float = 3.0


# 참여 관련 Request 스키마
class ParticipationStatusUpdateRequest(BaseRequest):
    """참여 상태 업데이트 (승인/거부/노쇼/완료)"""

    status: ParticipationStatusLiteral


# Q&A 관련 Request 스키마
class QuestionCreateRequest(BaseRequest):
    """질문 작성"""

    question: str
    is_private: bool = False


class AnswerCreateRequest(BaseRequest):
    """답변 작성"""

    answer: str


class QuestionUpdateRequest(BaseRequest):
    """질문 수정"""

    question: str
    is_private: bool | None = None


class AnswerUpdateRequest(BaseRequest):
    """답변 수정"""

    answer: str


# 평가 관련 Request 스키마
class RatingCreateRequest(BaseRequest):
    """평가 작성"""

    mogu_post_id: str
    reviewee_id: str
    stars: int
    keywords: list[RatingKeywordCodeLiteral] | None = None


class RatingUpdateRequest(BaseRequest):
    """평가 수정"""

    stars: int | None = None
    keywords: list[RatingKeywordCodeLiteral] | None = None


class PresignedUrlRequest(BaseRequest):
    """사전 서명 URL 생성 요청"""

    file_name: str = Field(..., min_length=1, max_length=255, description="파일명")
    bucket_name: str = Field(
        default="images", min_length=1, max_length=63, description="버킷명"
    )
