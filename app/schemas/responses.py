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


class QuestionAnswerResponse(BaseResponse):
    id: str
    questioner_id: str
    question: str
    answerer_id: str | None = None
    answer: str | None = None
    is_private: bool
    question_created_at: datetime
    answer_created_at: datetime | None = None


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
    questions_answers: list[dict[str, Any]] | None = None


class MoguPostListItemResponse(BaseResponse):
    """모구 게시물 목록용 최적화된 응답 스키마"""

    id: str
    title: str
    price: int
    category: str
    mogu_market: str
    mogu_datetime: datetime
    status: str
    target_count: int
    joined_count: int
    created_at: datetime
    thumbnail_image: str | None = None
    favorite_count: int  # 찜하기 개수


class MoguPostWithParticipationResponse(MoguPostListItemResponse):
    """참여 정보가 포함된 모구 게시물 응답 스키마"""

    # 참여 정보
    my_participation_status: str
    my_participation_applied_at: datetime
    my_participation_decided_at: datetime | None = None


class MoguPostListPaginatedResponse(BaseResponse):
    posts: list[MoguPostListItemResponse]
    pagination: dict[str, int]


class MoguPostWithParticipationPaginatedResponse(BaseResponse):
    posts: list[MoguPostWithParticipationResponse]
    pagination: dict[str, int]


# 참여 관련 Response 스키마
class ParticipationResponse(BaseResponse):
    user_id: str
    mogu_post_id: str
    status: str
    applied_at: datetime
    decided_at: datetime | None = None


class ParticipationWithUserResponse(BaseResponse):
    user_id: str
    status: str
    applied_at: datetime
    decided_at: datetime | None = None
    user: dict[str, str | None]


class ParticipationListResponse(BaseResponse):
    participants: list[ParticipationWithUserResponse]


class ParticipationMessageResponse(BaseResponse):
    message: str
    participation: ParticipationResponse | None = None


# Q&A 관련 Response 스키마
class QuestionResponse(BaseResponse):
    id: str
    mogu_post_id: str
    questioner_id: str
    question: str
    is_private: bool
    question_created_at: datetime
    questioner: dict[str, str | None]


class QuestionWithAnswerResponse(BaseResponse):
    id: str
    question: str
    answer: str | None = None
    is_private: bool
    question_created_at: datetime
    answer_created_at: datetime | None = None
    questioner: dict[str, str | None]
    answerer: dict[str, str | None] | None = None


class QuestionListResponse(BaseResponse):
    items: list[QuestionWithAnswerResponse]
