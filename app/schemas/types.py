"""공통 타입 정의"""

from typing import Literal

# CategoryEnum 값들
CategoryLiteral = Literal["생활용품", "식품/간식류", "패션/잡화", "뷰티/헬스케어"]

# MarketEnum 값들
MarketLiteral = Literal[
    "코스트코",
    "이마트",
    "트레이더스",
    "노브랜드",
    "편의점",
    "홈플러스",
    "동네마켓",
    "전통시장",
    "이커머스",
    "기타",
]

# PostStatusEnum 값들
PostStatusLiteral = Literal[
    "draft",
    "recruiting",
    "locked",
    "purchasing",
    "distributing",
    "completed",
    "canceled",
]

# ParticipationStatusEnum 값들
ParticipationStatusLiteral = Literal[
    "applied",
    "accepted",
    "rejected",
    "canceled",
    "no_show",
    "fulfilled",
]

# GenderEnum 값들
GenderLiteral = Literal["male", "female", "other"]

# HouseholdSizeEnum 값들
HouseholdSizeLiteral = Literal["1인", "2인", "3인", "4인 이상"]

# RatingKeywordTypeEnum 값들
RatingKeywordTypeLiteral = Literal["positive", "negative"]

# RatingKeywordMaster 코드들
RatingKeywordCodeLiteral = Literal[
    # Positive keywords
    "friendly_communication",
    "time_place_promise",
    "fast_settlement",
    "careful_product",
    "quick_response",
    "fresh_management",
    "trustworthy",
    "want_again",
    # Negative keywords
    "time_break",
    "unfriendly_communication",
    "late_settlement",
    "careless_product",
    "poor_packaging",
    "opaque_process",
    "inaccurate_photo",
    "refund_haggling",
]

# UserStatusEnum 값들
UserStatusLiteral = Literal[
    "pending_onboarding",
    "active",
    "inactive",
    "suspended",
]

# 정렬 옵션들
SortLiteral = Literal["ai_recommended", "recent", "distance"]
