"""Application enums for database and API."""

import enum


class GenderEnum(str, enum.Enum):
    """사용자 성별"""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class CategoryEnum(str, enum.Enum):
    """상품 카테고리"""

    HOUSEHOLD = "생활용품"
    FOOD_SNACKS = "식품/간식류"
    FASHION_ACCESSORIES = "패션/잡화"
    BEAUTY_HEALTHCARE = "뷰티/헬스케어"


class HouseholdSizeEnum(str, enum.Enum):
    """가구 수"""

    ONE = "1인"
    TWO = "2인"
    THREE = "3인"
    FOUR_OR_MORE = "4인 이상"


class MarketEnum(str, enum.Enum):
    """마켓 종류"""

    COSTCO = "코스트코"
    EMART = "이마트"
    TRADERS = "트레이더스"
    NO_BRAND = "노브랜드"
    CONVENIENCE_STORE = "편의점"  # GS25, CU, 7ELEVEN 등
    HOMEPLUS = "홈플러스"
    LOCAL_MARKET = "동네마켓"
    TRADITIONAL_MARKET = "전통시장"
    ECOMMERCE = "이커머스"  # coupang, SSG.COM, 11번가, NAVER, kakao 등
    OTHER = "기타"


class PostStatusEnum(str, enum.Enum):
    """게시글 상태 (향후 사용)"""

    DRAFT = "draft"
    RECRUITING = "recruiting"
    LOCKED = "locked"
    PURCHASING = "purchasing"
    DISTRIBUTING = "distributing"
    COMPLETED = "completed"
    CANCELED = "canceled"


class ParticipationStatusEnum(str, enum.Enum):
    """참여 상태 (향후 사용)"""

    APPLIED = "applied"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELED = "canceled"
    NO_SHOW = "no_show"
    FULFILLED = "fulfilled"


class UserStatusEnum(str, enum.Enum):
    """사용자 상태"""

    PENDING_ONBOARDING = "pending_onboarding"  # 온보딩 대기 (추가 정보 필요)
    ACTIVE = "active"  # 활성 사용자 (온보딩 완료)
    INACTIVE = "inactive"  # 비활성
    SUSPENDED = "suspended"  # 정지


class RatingKeywordTypeEnum(str, enum.Enum):
    """평가 키워드 타입"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
