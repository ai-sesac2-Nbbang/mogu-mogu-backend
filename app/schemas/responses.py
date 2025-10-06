from datetime import date, datetime
from typing import TYPE_CHECKING, TypedDict

from geoalchemy2.shape import to_shape
from pydantic import BaseModel, ConfigDict, EmailStr

if TYPE_CHECKING:
    from app.models import (
        MoguPost,
        Participation,
        QuestionAnswer,
        Rating,
        RatingKeywordMaster,
        User,
    )


class PaginationInfo(TypedDict):
    """페이지네이션 정보 타입"""

    page: int
    limit: int
    total: int
    total_pages: int


class DeadlineInfo(TypedDict):
    """평가 마감 정보 타입"""

    completed_at: str
    deadline: str
    remaining_hours: int
    is_expired: bool


class ImageInfo(TypedDict, total=False):
    """이미지 정보 타입"""

    id: str
    image_path: str
    order: int
    is_thumbnail: bool


class PresignedUrlResponse(BaseModel):
    """사전 서명 URL 응답"""

    upload_url: str
    file_path: str
    expires_in: int
    bucket_name: str


class ParticipationInfo(TypedDict):
    """참여 정보 타입"""

    status: str
    applied_at: str
    decided_at: str | None


class UserBasicInfo(TypedDict):
    """사용자 기본 정보 타입"""

    id: str
    nickname: str | None
    profile_image_path: str | None


class QuestionAnswerInfo(TypedDict):
    """질문답변 정보 타입"""

    id: str
    questioner_id: str
    question: str
    answerer_id: str | None
    answer: str | None
    is_private: bool
    question_created_at: str
    answer_created_at: str | None


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
    profile_image_path: str | None = None

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

    @classmethod
    def from_user(cls, user: "User") -> "UserResponse":
        """User 모델로부터 UserResponse를 생성합니다."""
        return cls(
            user_id=user.id,
            email=user.email,
            kakao_id=user.kakao_id,
            provider=user.provider,
            nickname=user.nickname,
            profile_image_path=user.profile_image_path,
            name=user.name,
            phone_number=user.phone_number,
            birth_date=user.birth_date,
            gender=user.gender,
            interested_categories=user.interested_categories,
            household_size=user.household_size,
            wish_markets=user.wish_markets,
            wish_times=user.wish_times,
            status=user.status,
            reported_count=user.reported_count,
            onboarded_at=user.onboarded_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class WishSpotResponse(BaseResponse):
    id: int
    label: str
    latitude: float
    longitude: float
    created_at: datetime


class WishSpotListResponse(BaseResponse):
    items: list[WishSpotResponse]


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

    @classmethod
    def from_keyword_master(
        cls, keyword: "RatingKeywordMaster"
    ) -> "RatingKeywordMasterResponse":
        """RatingKeywordMaster 모델로부터 RatingKeywordMasterResponse를 생성합니다."""
        return cls(
            id=keyword.id,
            code=keyword.code,
            name_kr=keyword.name_kr,
            type=keyword.type,
            created_at=keyword.created_at,
        )


# 프론트엔드 UI 지원을 위한 추가 Response 스키마
class ReviewableUserResponse(BaseResponse):
    """리뷰 가능한 사용자 응답"""

    user_id: str
    nickname: str | None = None
    profile_image_path: str | None = None
    participation_status: str
    rating_id: str | None = None  # 작성된 리뷰의 ID (null이면 리뷰 미작성)

    @classmethod
    def from_participation(
        cls,
        participation: "Participation",
        rating_id: str | None = None,
    ) -> "ReviewableUserResponse":
        """Participation 모델로부터 ReviewableUserResponse를 생성합니다."""
        return cls(
            user_id=participation.user.id,
            nickname=participation.user.nickname or "익명",
            profile_image_path=participation.user.profile_image_path,
            participation_status=participation.status,
            rating_id=rating_id,
        )

    @classmethod
    def from_user(
        cls,
        user: "User",
        participation_status: str,
        rating_id: str | None = None,
    ) -> "ReviewableUserResponse":
        """User 모델로부터 ReviewableUserResponse를 생성합니다."""
        return cls(
            user_id=user.id,
            nickname=user.nickname or "익명",
            profile_image_path=user.profile_image_path,
            participation_status=participation_status,
            rating_id=rating_id,
        )


class ReviewableUsersResponse(BaseResponse):
    """리뷰 가능한 사용자 목록 응답"""

    items: list[ReviewableUserResponse]


class RatingStatusResponse(BaseResponse):
    """평가 상태 응답"""

    can_review: bool
    reviewable_users: list[ReviewableUserResponse] | None = None
    reason: str | None = None
    deadline_info: DeadlineInfo | None = None


# 모구 게시물 관련 Response 스키마
class MoguSpotResponse(BaseResponse):
    latitude: float
    longitude: float


class MoguPostImageResponse(BaseResponse):
    id: str
    image_path: str
    sort_order: int
    is_thumbnail: bool


class MoguPostUserResponse(BaseResponse):
    id: str
    nickname: str
    profile_image_path: str | None = None


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
    labor_fee: int
    category: str
    mogu_market: str
    mogu_spot: dict[str, float]
    mogu_datetime: datetime
    status: str
    target_count: int | None = None
    joined_count: int
    created_at: datetime
    images: list[ImageInfo] | None = None
    user: UserBasicInfo
    my_participation: ParticipationInfo | None = None
    is_favorited: bool | None = None
    questions_answers: list[QuestionAnswerInfo] | None = None

    @classmethod
    def from_mogu_post(
        cls,
        mogu_post: "MoguPost",
        my_participation: ParticipationInfo | None = None,
        is_favorited: bool = False,
        questions_answers: list[QuestionAnswerInfo] | None = None,
    ) -> "MoguPostResponse":
        """MoguPost 모델로부터 MoguPostResponse를 생성합니다."""
        # Shapely를 사용한 위도/경도 추출
        point = to_shape(mogu_post.mogu_spot)
        latitude = point.y
        longitude = point.x

        return cls(
            id=mogu_post.id,
            user_id=mogu_post.user_id,
            title=mogu_post.title,
            description=mogu_post.description,
            price=mogu_post.price,
            labor_fee=mogu_post.labor_fee,
            category=mogu_post.category,
            mogu_market=mogu_post.mogu_market,
            mogu_spot={
                "latitude": latitude,
                "longitude": longitude,
            },
            mogu_datetime=mogu_post.mogu_datetime,
            status=mogu_post.status,
            target_count=mogu_post.target_count,
            joined_count=mogu_post.joined_count,
            created_at=mogu_post.created_at,
            images=[
                {
                    "id": img.id,
                    "image_path": img.image_path,
                    "order": img.sort_order,
                }
                for img in mogu_post.images
            ],
            user={
                "id": mogu_post.user.id,
                "nickname": mogu_post.user.nickname,
                "profile_image_path": mogu_post.user.profile_image_path,
            },
            my_participation=my_participation,
            is_favorited=is_favorited,
            questions_answers=questions_answers,
        )


class MoguPostListItemResponse(BaseResponse):
    """모구 게시물 목록용 최적화된 응답 스키마"""

    id: str
    title: str
    price: int
    labor_fee: int
    category: str
    mogu_market: str
    mogu_datetime: datetime
    status: str
    target_count: int
    joined_count: int
    created_at: datetime
    thumbnail_image: str | None = None
    favorite_count: int  # 찜하기 개수


class MoguPostListItemWithReviewResponse(MoguPostListItemResponse):
    """리뷰 정보가 포함된 모구 게시물 목록 응답 스키마"""

    can_review: bool = False  # 리뷰 작성 가능 여부


class MoguPostWithParticipationResponse(MoguPostListItemResponse):
    """참여 정보가 포함된 모구 게시물 응답 스키마"""

    # 참여 정보
    my_participation_status: str
    my_participation_applied_at: datetime
    my_participation_decided_at: datetime | None = None
    can_review: bool = False  # 리뷰 작성 가능 여부


class MoguPostListPaginatedResponse(BaseResponse):
    items: list[MoguPostListItemResponse]
    pagination: PaginationInfo


class MoguPostListWithReviewPaginatedResponse(BaseResponse):
    items: list[MoguPostListItemWithReviewResponse]
    pagination: PaginationInfo


class MoguPostWithParticipationPaginatedResponse(BaseResponse):
    items: list[MoguPostWithParticipationResponse]
    pagination: PaginationInfo


class MoguPostFavoritesPaginatedResponse(BaseResponse):
    items: list[MoguPostListItemResponse]
    pagination: PaginationInfo


# 참여 관련 Response 스키마
class ParticipationResponse(BaseResponse):
    user_id: str
    mogu_post_id: str
    status: str
    applied_at: datetime
    decided_at: datetime | None = None

    @classmethod
    def from_participation(
        cls, participation: "Participation"
    ) -> "ParticipationResponse":
        """Participation 모델로부터 ParticipationResponse를 생성합니다."""
        return cls(
            user_id=participation.user_id,
            mogu_post_id=participation.mogu_post_id,
            status=participation.status,
            applied_at=participation.applied_at,
            decided_at=participation.decided_at,
        )


class ParticipationWithUserResponse(BaseResponse):
    user_id: str
    status: str
    applied_at: datetime
    decided_at: datetime | None = None
    user: UserBasicInfo


class ParticipationListResponse(BaseResponse):
    items: list[ParticipationWithUserResponse]


# Q&A 관련 Response 스키마
class QuestionResponse(BaseResponse):
    id: str
    mogu_post_id: str
    questioner_id: str
    question: str
    is_private: bool
    question_created_at: datetime
    questioner: UserBasicInfo


class QuestionWithAnswerResponse(BaseResponse):
    id: str
    question: str
    answer: str | None = None
    is_private: bool
    question_created_at: datetime
    answer_created_at: datetime | None = None
    questioner: UserBasicInfo
    answerer: UserBasicInfo | None = None

    @classmethod
    def from_question(
        cls, question: "QuestionAnswer", answerer_data: UserBasicInfo | None = None
    ) -> "QuestionWithAnswerResponse":
        """QuestionAnswer 모델로부터 QuestionWithAnswerResponse를 생성합니다."""
        return cls(
            id=question.id,
            question=question.question,
            answer=question.answer,
            is_private=question.is_private,
            question_created_at=question.question_created_at,
            answer_created_at=question.answer_created_at,
            questioner={
                "id": question.questioner.id,
                "nickname": question.questioner.nickname,
                "profile_image_path": question.questioner.profile_image_path,
            },
            answerer=answerer_data,
        )


class QuestionListResponse(BaseResponse):
    items: list[QuestionWithAnswerResponse]


# 유틸리티 클래스
class QuestionAnswerConverter:
    """Q&A 데이터 변환을 위한 유틸리티 클래스"""

    @staticmethod
    def to_dict_list(
        questions_answers: list["QuestionAnswer"] | None,
    ) -> list[QuestionAnswerInfo] | None:
        """Q&A 데이터를 딕셔너리 형태로 변환합니다."""
        if not questions_answers:
            return None

        return [
            {
                "id": qa.id,
                "questioner_id": qa.questioner_id,
                "question": qa.question,
                "answerer_id": qa.answerer_id,
                "answer": qa.answer,
                "is_private": qa.is_private,
                "question_created_at": qa.question_created_at.isoformat(),
                "answer_created_at": (
                    qa.answer_created_at.isoformat() if qa.answer_created_at else None
                ),
            }
            for qa in questions_answers
        ]

    @staticmethod
    def build_answerer_data(question: "QuestionAnswer") -> UserBasicInfo | None:
        """답변자 정보를 구성합니다."""
        if question.answerer:
            return {
                "id": question.answerer.id,
                "nickname": question.answerer.nickname,
                "profile_image_path": question.answerer.profile_image_path,
            }
        return None


# 평가 관련 Response 스키마
class RatingResponse(BaseResponse):
    """평가 응답"""

    id: str
    mogu_post_id: str
    reviewer_id: str
    reviewee_id: str
    stars: int
    keywords: list[str] | None = None
    created_at: datetime

    @classmethod
    def from_rating(cls, rating: "Rating") -> "RatingResponse":
        """Rating 모델로부터 RatingResponse를 생성합니다."""
        return cls(
            id=rating.id,
            mogu_post_id=rating.mogu_post_id,
            reviewer_id=rating.reviewer_id,
            reviewee_id=rating.reviewee_id,
            stars=rating.stars,
            keywords=rating.keywords,
            created_at=rating.created_at,
        )


class RatingWithReviewerResponse(BaseResponse):
    """평가자 정보가 포함된 평가 응답"""

    id: str
    mogu_post_id: str
    reviewer_id: str
    reviewee_id: str
    stars: int
    keywords: list[str] | None = None
    created_at: datetime
    reviewer: UserBasicInfo

    @classmethod
    def from_rating(cls, rating: "Rating") -> "RatingWithReviewerResponse":
        """Rating 모델로부터 RatingWithReviewerResponse를 생성합니다."""
        return cls(
            id=rating.id,
            mogu_post_id=rating.mogu_post_id,
            reviewer_id=rating.reviewer_id,
            reviewee_id=rating.reviewee_id,
            stars=rating.stars,
            keywords=rating.keywords,
            created_at=rating.created_at,
            reviewer={
                "id": rating.reviewer.id,
                "nickname": rating.reviewer.nickname,
                "profile_image_path": rating.reviewer.profile_image_path,
            },
        )


class RatingListResponse(BaseResponse):
    """평가 목록 응답"""

    items: list[RatingWithReviewerResponse]


class MyRatingsResponse(BaseResponse):
    """내가 작성한 리뷰 목록 응답"""

    items: list[RatingWithReviewerResponse]


class RatingKeywordListResponse(BaseResponse):
    """평가 키워드 목록 응답"""

    items: list[RatingKeywordMasterResponse]


class UserKeywordStatsResponse(BaseResponse):
    """사용자 키워드 통계 응답"""

    keyword_code: str
    name_kr: str
    count: int


class UserKeywordStatsListResponse(BaseResponse):
    """사용자 키워드 통계 목록 응답"""

    items: list[UserKeywordStatsResponse]
