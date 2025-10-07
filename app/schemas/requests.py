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
    profile_image_path: str | None = None

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

    image_path: str
    sort_order: int
    is_thumbnail: bool


class MoguPostCreateRequest(BaseRequest):
    """모구 게시물 생성"""

    title: str
    description: str
    price: int = Field(gt=0, description="가격 (0보다 큰 값)")
    labor_fee: int = Field(default=0, ge=0, description="수고비 (0 이상)")
    category: CategoryLiteral
    mogu_market: MarketLiteral
    mogu_spot: MoguSpotRequest
    mogu_datetime: datetime
    target_count: int = Field(ge=1, description="목표 인원 (1명 이상)")
    images: list[MoguPostImageRequest] | None = None

    @field_validator("mogu_datetime")
    @classmethod
    def validate_mogu_datetime(cls, v: datetime) -> datetime:
        """모구 일시 검증: 미래 날짜여야 함"""
        now = datetime.now()

        if v <= now:
            raise ValueError("모구 일시는 미래 날짜여야 합니다.")

        return v


class MoguPostUpdateRequest(BaseRequest):
    """모구 게시물 수정"""

    title: str | None = None
    description: str | None = None
    price: int | None = Field(default=None, gt=0, description="가격 (0보다 큰 값)")
    labor_fee: int | None = Field(default=None, ge=0, description="수고비 (0 이상)")
    category: CategoryLiteral | None = None
    mogu_market: MarketLiteral | None = None
    mogu_spot: MoguSpotRequest | None = None
    mogu_datetime: datetime | None = None
    target_count: int | None = Field(
        default=None, ge=1, description="목표 인원 (1명 이상)"
    )
    status: PostStatusLiteral | None = None
    images: list[MoguPostImageRequest] | None = None

    @field_validator("mogu_datetime")
    @classmethod
    def validate_mogu_datetime(cls, v: datetime | None) -> datetime | None:
        """모구 일시 검증: 미래 날짜여야 함"""
        if v is None:
            return v

        now = datetime.now()

        if v <= now:
            raise ValueError("모구 일시는 미래 날짜여야 합니다.")

        return v


class MoguPostListQueryParams(BaseRequest):
    """모구 게시물 목록 조회 쿼리 파라미터"""

    page: int = Field(default=1, ge=1, description="페이지 번호 (1번 이상)")
    size: int = Field(default=20, ge=1, description="페이지당 항목 수 (1개 이상)")
    sort: SortLiteral = "ai_recommended"
    category: CategoryLiteral | None = None
    mogu_market: MarketLiteral | None = None
    status: PostStatusLiteral | None = (
        "recruiting"  # 기본값은 recruiting, None이면 모든 상태 조회
    )
    latitude: float = Field(ge=-90, le=90, description="위도 (-90~90)")
    longitude: float = Field(ge=-180, le=180, description="경도 (-180~180)")
    radius: float = Field(
        default=3.0, ge=0.1, le=10, description="검색 반경 (0.1~10km)"
    )


# 참여 관련 Request 스키마
class ParticipationStatusUpdateRequest(BaseRequest):
    """참여 상태 업데이트 (승인/거부/노쇼/완료)"""

    status: ParticipationStatusLiteral


# 댓글 관련 Request 스키마
class CommentCreateRequest(BaseRequest):
    """댓글 작성"""

    content: str


# 평가 관련 Request 스키마
class RatingCreateRequest(BaseRequest):
    """평가 작성"""

    mogu_post_id: str
    reviewee_id: str
    stars: int = Field(ge=1, le=5, description="별점 (1-5)")
    keywords: list[RatingKeywordCodeLiteral] | None = None


class RatingUpdateRequest(BaseRequest):
    """평가 수정"""

    stars: int | None = Field(default=None, ge=1, le=5, description="별점 (1-5)")
    keywords: list[RatingKeywordCodeLiteral] | None = None


class PresignedUrlRequest(BaseRequest):
    """사전 서명 URL 생성 요청"""

    file_name: str = Field(..., min_length=1, max_length=255, description="파일명")
    bucket_name: str = Field(
        default="images", min_length=1, max_length=63, description="버킷명"
    )


class ImageDeleteRequest(BaseRequest):
    """이미지 삭제 요청"""

    file_paths: list[str] = Field(
        ..., min_length=1, description="삭제할 이미지 파일 경로 목록"
    )
    bucket_name: str = Field(
        default="images", min_length=1, max_length=63, description="버킷명"
    )
