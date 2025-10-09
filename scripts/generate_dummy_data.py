#!/usr/bin/env python3
"""
모구 AI 추천 시스템을 위한 더미 데이터 생성 스크립트

이 스크립트는 다음과 같은 데이터를 생성합니다:
1. 페르소나 기반 사용자 프로필
2. 현실적인 모구 게시물 데이터
3. 사용자 상호작용 패턴 (참여, 찜하기, 평가)
4. 위치 기반 데이터 (서울 지역)
"""

import asyncio
import copy
import gzip
import heapq
import json
import logging
import math
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

# 상수 정의
EVENING_PROBABILITY = 0.7  # 70% 확률
WEEKEND_PROBABILITY = 0.4  # 40% 확률
POWER_USER_PROBABILITY = 0.05  # 5% 확률
ACTIVE_USER_TWO_SPOTS_PROBABILITY = 0.6  # 60% 확률
WEEKDAY_THRESHOLD = 5  # 평일 임계값
ACTIVE_USER_PROBABILITY = 0.8  # 80% 확률
FRESHNESS_HOURS = 24  # 24시간
MAX_CATEGORIES = 3  # 최대 카테고리 수
MAX_MARKETS = 3  # 최대 마켓 수

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

# 재현성을 위한 고정 기준 시각 (KST)
BASE_NOW = datetime(
    2025, 10, 8, 15, 0, 0, tzinfo=KST
)  # 2025년 10월 8일 오후 3시 (발표 직전)

# 발표일 보장 상수 (KST)
PRESENTATION_DAY = datetime(2025, 10, 13, 0, 0, 0, tzinfo=KST)  # 발표일: 10월 13일


@dataclass(frozen=True)
class Config:
    """더미 데이터 생성 설정"""

    num_users: int = 1000
    num_posts: int = 5000
    recruiting_quota_ratio: float = 0.2
    max_candidates_k: int = 800
    max_distance_km: float = 6.0
    min_candidates_threshold: int = 300
    cache_precision_digits: int = 5  # 거리 캐시 정규화 (≈1m)


CFG = Config()

# 성능 최적화 상수 (Config로 이전됨)
MIN_CANDIDATES_THRESHOLD = CFG.min_candidates_threshold
STUDENT_COST_THRESHOLDS = {
    "very_low": 5000,
    "low": 8000,
    "medium": 12000,
    "high": 15000,
}
AGE_THRESHOLDS = {
    "young_adult_start": 20,
    "young_adult_end": 30,
    "middle_aged": 40,
}
NOISE_PROBABILITY = 0.15  # 15% 확률
TIME_MATCH_PROBABILITY = 0.7  # 70% 확률
ACCEPTED_PROBABILITY = 0.75  # 75% 확률
FULFILLED_PROBABILITY = 0.80  # 80% 확률
REJECTED_PROBABILITY = 0.08  # 8% 확률
CANCELED_PROBABILITY = 0.10  # 10% 확률
NO_SHOW_PROBABILITY = 0.02  # 2% 확률
RATING_PROBABILITY = 0.7  # 70% 확률
RATING_THRESHOLD_HIGH = 4  # 높은 평점 임계값
RATING_THRESHOLD_LOW = 2  # 낮은 평점 임계값


def unique_keep_order(seq: list[Any]) -> list[Any]:
    """순서를 보존하면서 중복 제거 (재현성 보장)"""
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def make_wish_times(hours: tuple[int, ...]) -> list[int]:
    """선호 시간대 배열 생성 (24시간 기준)"""
    wish_times = [0] * 24
    for hour in hours:
        wish_times[hour] = 1
    return wish_times


# 페르소나 정의
PERSONAS: list[dict[str, Any]] = [
    dict(
        email="persona1@mogumogu.dev",
        nickname="P1_OfficeWorker_Gangnam",
        gender="male",
        birth_date=date(1994, 5, 12),
        household_size="1인",
        interested_categories=["식품/간식류", "생활용품"],
        wish_markets=["편의점", "이마트"],
        wish_times=make_wish_times((19, 20, 21, 22)),
        wish_spots=[("집", (37.498, 127.027)), ("회사", (37.501, 127.025))],
        status="active",
    ),
    dict(
        email="persona2@mogumogu.dev",
        nickname="P2_Family_Costco_Suwon",
        gender="female",
        birth_date=date(1988, 8, 3),
        household_size="4인 이상",
        interested_categories=["생활용품", "식품/간식류"],
        wish_markets=["코스트코", "홈플러스"],
        wish_times=make_wish_times((9, 10, 11, 12)),
        wish_spots=[("집", (37.263, 127.028)), ("코스트코", (37.245, 127.032))],
        status="active",
    ),
    dict(
        email="persona3@mogumogu.dev",
        nickname="P3_Fashion_Beauty_Hongdae",
        gender="female",
        birth_date=date(1999, 2, 1),
        household_size="2인",
        interested_categories=["패션/잡화", "뷰티/헬스케어"],
        wish_markets=["이커머스", "동네마켓"],
        wish_times=make_wish_times((20, 21, 22, 23)),
        wish_spots=[("집", (37.557, 126.923))],
        status="active",
    ),
    dict(
        email="persona4@mogumogu.dev",
        nickname="P4_NightShifter_Incheon",
        gender="male",
        birth_date=date(1992, 11, 23),
        household_size="3인",
        interested_categories=["생활용품"],
        wish_markets=["전통시장", "노브랜드"],
        wish_times=make_wish_times((22, 23, 0, 1)),
        wish_spots=[("집", (37.476, 126.616))],
        status="active",
    ),
    dict(
        email="persona5@mogumogu.dev",
        nickname="P5_Student_Sindorim",
        gender="female",
        birth_date=date(2002, 6, 14),
        household_size="1인",
        interested_categories=["식품/간식류", "패션/잡화"],
        wish_markets=["편의점", "노브랜드"],
        wish_times=make_wish_times((18, 19, 20, 21, 22, 23)),
        wish_spots=[("집", (37.509, 126.889))],
        status="active",
    ),
]

# 서울 지역 좌표 데이터 (25개 구, 중복 제거)
SEOUL_LOCATIONS = [
    ("강남구", (37.517, 127.047)),
    ("서초구", (37.484, 127.033)),
    ("송파구", (37.514, 127.105)),
    ("강동구", (37.530, 127.123)),
    ("마포구", (37.566, 126.901)),
    ("용산구", (37.538, 126.965)),
    ("성동구", (37.563, 127.037)),
    ("광진구", (37.538, 127.082)),
    ("동대문구", (37.574, 127.040)),
    ("중랑구", (37.606, 127.092)),
    ("성북구", (37.589, 127.016)),
    ("강북구", (37.639, 127.025)),
    ("도봉구", (37.668, 127.047)),
    ("노원구", (37.654, 127.056)),
    ("은평구", (37.602, 126.929)),
    ("서대문구", (37.579, 126.936)),
    ("종로구", (37.573, 126.978)),
    ("중구", (37.564, 126.997)),
    ("영등포구", (37.526, 126.896)),
    ("동작구", (37.512, 126.939)),
    ("관악구", (37.475, 126.951)),
]

# 카테고리별 구체적인 상품 데이터 (대용량 구매 중심으로 재분류)
CATEGORY_PRODUCTS = {
    "생활용품": [
        "크리넥스 3겹 화장지 30롤",
        "베베숲 물티슈 캡형 10팩",
        "다우니 섬유유연제 4L 리필",
        "리스테린 1L x 2개",
        "페브리즈 1L 리필 x 2개",
        "종량제봉투 100L 100매",
        "듀라셀 건전지 AA 40개입",
        "질레트 퓨전 면도날 8개입",
        "아리얼 세탁세제 4kg",
        "스카트브리트 청소용품 세트",
        "코스트코 종이컵 1000개입",
        "스카트 키친타월 200매 12롤",
        "크리넥스 안심물티슈 캡형 100매 10팩",
        "에티카 일회용 비말차단 마스크 100매",
        "오공 라텍스 요리용 장갑 100매 박스",
        "로얄캐닌 강아지사료 8kg",
    ],
    "식품/간식류": [
        "코스트코 소불고기 (4kg)",
        "신라면 40개입 1박스",
        "제주 삼다수 2L 12병",
        "하림 냉동 닭가슴살 2kg",
        "비비고 왕교자 1.5kg x 2개",
        "햇반 24개입 1박스",
        "커클랜드 아몬드 1.13kg",
        "필라델피아 크림치즈 1.36kg",
        "상하목장 유기농우유 24팩",
        "네스프레소 호환캡슐 100개입",
        "농심 신라면 120개입",
        "오뚜기 진라면 40개입",
        "동원 참치캔 24개입",
        "CJ 햇반 48개입",
        "롯데 초코파이 30개입",
    ],
    "패션/잡화": [
        "나이키 스포츠 양말 6족 세트",
        "유니클로 에어리즘 3팩",
        "무신사 스탠다드 기본티 5장",
        "크록스 지비츠 세트 (20개입)",
        "캘빈클라인 드로즈 3팩",
        "피카소 칫솔 20개입",
        "컨버스 척 70 클래식",
        "잔스포츠 백팩",
        "아디다스 운동화",
        "나이키 후드티",
        "유니클로 히트텍 3팩",
        "무지 양말 10족 세트",
        "크록스 클래식 슬리퍼",
        "캘빈클라인 벨트",
        "시계 스트랩 5개 세트",
    ],
    "뷰티/헬스케어": [
        "닥터지 선크림 1+1 기획세트",
        "고려은단 비타민C 300정",
        "KF94 마스크 200매 박스",
        "메디힐 마스크팩 30매 박스",
        "세타필 대용량 로션 591ml",
        "종근당 락토핏 골드 180포",
        "아베다 샴푸 1L",
        "바이오가이아 유산균",
        "라네즈 워터뱅크 크림 100ml",
        "설화수 자음생크림 60ml",
        "이니스프리 그린티 씨드 세럼",
        "헤라 선크림 50ml",
        "에뛰드하우스 선크림 60ml",
        "아토팜 베이비 로션 500ml",
        "무지개약국 종합비타민 180정",
    ],
}

# 마켓별 특성
MARKET_CHARACTERISTICS = {
    "코스트코": {
        "price_range": (10000, 100000),
        "bulk_tendency": True,
        "categories": ["생활용품", "식품/간식류"],
    },
    "이마트": {
        "price_range": (1000, 50000),
        "bulk_tendency": False,
        "categories": ["생활용품", "식품/간식류", "패션/잡화"],
    },
    "트레이더스": {
        "price_range": (5000, 80000),
        "bulk_tendency": True,
        "categories": ["생활용품", "식품/간식류"],
    },
    "노브랜드": {
        "price_range": (500, 20000),
        "bulk_tendency": False,
        "categories": ["생활용품", "식품/간식류"],
    },
    "편의점": {
        "price_range": (1000, 15000),
        "bulk_tendency": False,
        "categories": ["식품/간식류", "생활용품"],
    },
    "홈플러스": {
        "price_range": (2000, 30000),
        "bulk_tendency": False,
        "categories": ["생활용품", "식품/간식류", "패션/잡화"],
    },
    "동네마켓": {
        "price_range": (1000, 10000),
        "bulk_tendency": False,
        "categories": ["식품/간식류", "생활용품"],
    },
    "전통시장": {
        "price_range": (500, 5000),
        "bulk_tendency": False,
        "categories": ["식품/간식류", "생활용품"],
    },
    "이커머스": {
        "price_range": (1000, 100000),
        "bulk_tendency": False,
        "categories": ["패션/잡화", "뷰티/헬스케어"],
    },
    "기타": {
        "price_range": (1000, 50000),
        "bulk_tendency": False,
        "categories": ["생활용품", "식품/간식류", "패션/잡화", "뷰티/헬스케어"],
    },
}


def generate_random_location() -> tuple[float, float]:
    """서울 지역 내 랜덤 좌표 생성"""
    base_lat, base_lon = random.choice(SEOUL_LOCATIONS)[1]
    # ±0.01도 범위 내에서 랜덤 오프셋
    lat_offset = random.uniform(-0.01, 0.01)
    lon_offset = random.uniform(-0.01, 0.01)
    return (base_lat + lat_offset, base_lon + lon_offset)


def generate_realistic_datetime(days_back: int = 30) -> datetime:
    """현실적인 날짜/시간 생성 (BASE_NOW 기준)"""
    random_days = random.randint(0, days_back)
    random_hours = random.randint(0, 23)
    random_minutes = random.randint(0, 59)

    return BASE_NOW - timedelta(
        days=random_days, hours=random_hours, minutes=random_minutes
    )


def after_time(base_time: datetime, min_minutes: int, max_minutes: int) -> datetime:
    """기준 시간 이후의 시간 생성 (단조 증가 보장)"""
    minutes_offset = random.randint(min_minutes, max_minutes)
    return base_time + timedelta(minutes=minutes_offset)


def clamp_after(t: datetime, min_t: datetime) -> datetime:
    """시간이 최소 시간 이후가 되도록 클램프"""
    return t if t >= min_t else min_t + timedelta(minutes=random.randint(1, 30))


def summarize_prices(posts: list[dict[str, Any]]) -> None:
    """가격 분포 요약 통계 출력"""
    by_cat: dict[str, list[int]] = {}
    for p in posts:
        by_cat.setdefault(p["category"], []).append(p["price"])

    print("\n💰 가격 분포 요약:")
    for cat, arr in by_cat.items():
        if not arr:  # 빈 배열 처리
            continue
        arr.sort()
        n = len(arr)
        mid = arr[n // 2]
        # 인덱스 안전성 강화: 클램프 적용
        p10_idx = max(0, int(n * 0.1))
        p90_idx = min(n - 1, int(n * 0.9))
        p10 = arr[p10_idx]
        p90 = arr[p90_idx]
        print(f"   [{cat}] n={n} median={mid:,} p10={p10:,} p90={p90:,}")


def generate_user_profiles(num_users: int = 1000) -> list[dict[str, Any]]:
    """사용자 프로필 생성 (현실적 분포 적용)"""
    profiles = []

    # 페르소나 5명 고정 (회귀 테스트용) - 딥카피로 안전한 복사
    persona_profiles = []
    for persona in PERSONAS:
        profile = copy.deepcopy(persona)
        profile["id"] = str(uuid.uuid4())
        profile["email"] = persona["email"]
        profile["nickname"] = persona["nickname"]
        profile["status"] = "active"
        profile["reported_count"] = 0
        profile["created_at"] = generate_realistic_datetime(90)
        profile["onboarded_at"] = profile["created_at"]
        persona_profiles.append(profile)

    profiles.extend(persona_profiles)

    # 나머지 사용자 생성 (995명)
    for i in range(num_users - 5):
        # 성별 분포: male 50%, female 50%
        gender = random.choices(["male", "female"], weights=[0.5, 0.5])[0]

        # 가구수 분포: 1인 40%, 2인 35%, 3인 15%, 4인 이상 10%
        household_size = random.choices(
            ["1인", "2인", "3인", "4인 이상"], weights=[0.40, 0.35, 0.15, 0.10]
        )[0]

        # 상태 분포: active 75%, pending_onboarding 10%, inactive 10%, suspended 5%
        status = random.choices(
            ["active", "pending_onboarding", "inactive", "suspended"],
            weights=[0.75, 0.10, 0.10, 0.05],
        )[0]

        # 생년월일: 1975-2006 균등 분포
        birth_year = random.randint(1975, 2006)
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)  # 안전하게 28일까지
        birth_date = date(birth_year, birth_month, birth_day)

        # 관심 카테고리: 식품/간식류 45%, 생활용품 35%, 패션/잡화 12%, 뷰티/헬스케어 8%
        category_weights = [0.45, 0.35, 0.12, 0.08]
        categories = ["식품/간식류", "생활용품", "패션/잡화", "뷰티/헬스케어"]
        num_categories = random.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]
        interested_categories = random.choices(
            categories, weights=category_weights, k=num_categories
        )
        interested_categories = unique_keep_order(
            interested_categories
        )  # 순서 보존 중복 제거

        # 위시 마켓: 대형 마트 중심 + 현실적 분포 (대형마트 60%, 기타 40%)
        market_weights = [
            0.25,  # 코스트코 (대용량 특화)
            0.20,  # 이마트 (대형마트)
            0.15,  # 노브랜드 (대형마트)
            0.10,  # 홈플러스 (대형마트)
            0.08,  # 편의점 (소형 구매)
            0.08,  # 동네마켓 (지역 특화)
            0.07,  # 이커머스 (온라인)
            0.05,  # 전통시장 (지역 특화)
            0.02,  # 기타
        ]
        markets = [
            "코스트코",
            "이마트",
            "노브랜드",
            "홈플러스",
            "편의점",
            "동네마켓",
            "이커머스",
            "전통시장",
            "기타",
        ]
        num_markets = random.choices([1, 2, 3], weights=[0.4, 0.4, 0.2])[0]
        wish_markets = random.choices(markets, weights=market_weights, k=num_markets)
        wish_markets = unique_keep_order(wish_markets)  # 순서 보존 중복 제거

        # 선호 시간대: 3-6개 시간대 선택, 평일 저녁(19-22)과 주말 오전/오후 비중 높게
        wish_times = [0] * 24
        num_time_slots = random.randint(3, 6)

        # 평일 저녁 시간대 (19-22) 높은 확률
        evening_slots = [19, 20, 21, 22]
        for slot in evening_slots:
            if random.random() < EVENING_PROBABILITY and num_time_slots > 0:
                wish_times[slot] = 1
                num_time_slots = max(0, num_time_slots - 1)

        # 주말 오전/오후 시간대 (9-12, 14-17) 중간 확률
        weekend_slots = [9, 10, 11, 12, 14, 15, 16, 17]
        for slot in weekend_slots:
            if num_time_slots <= 0:
                break
            if random.random() < WEEKEND_PROBABILITY:
                wish_times[slot] = 1
                num_time_slots = max(0, num_time_slots - 1)

        # 신고 횟수: 대부분 0, 1은 5% 미만, 2+는 극소수
        reported_count = random.choices([0, 1, 2, 3], weights=[0.92, 0.05, 0.02, 0.01])[
            0
        ]

        # Power User 설정 (5% 확률)
        is_power_user = random.random() < POWER_USER_PROBABILITY

        profile = {
            "id": str(uuid.uuid4()),
            "email": f"user_{i}@mogumogu.dev",
            "nickname": f"user_{i:03d}",
            "gender": gender,
            "birth_date": birth_date,
            "household_size": household_size,
            "interested_categories": interested_categories,
            "wish_markets": wish_markets,
            "wish_times": wish_times,
            "status": status,
            "reported_count": reported_count,
            "is_power_user": is_power_user,  # Power User 플래그 추가
            "created_at": generate_realistic_datetime(90),
            "onboarded_at": (
                generate_realistic_datetime(90) if status == "active" else None
            ),
        }

        profiles.append(profile)

    return profiles


def generate_user_wish_spots(
    user_profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """사용자 위시스팟 생성 (SEOUL_LOCATIONS 기반 현실적 분포)"""
    wish_spots = []

    # SEOUL_LOCATIONS을 활용한 현실적 지역 분포
    # 인구 밀도와 상업 지역을 고려한 가중치 설정 (21개 구)
    # 시각화를 위한 지역별 특성화
    location_weights = [
        0.15,  # 강남구 (상업 중심지) - 고가 상품, 패션/뷰티
        0.12,  # 서초구 (강남 인접) - 고가 상품, 패션/뷰티
        0.10,  # 송파구 (잠실, 올림픽공원) - 중가 상품, 생활용품
        0.08,  # 강동구 (강남 인접) - 중가 상품, 생활용품
        0.08,  # 마포구 (홍대) - 저가 상품, 식품/간식
        0.07,  # 용산구 (이태원) - 중가 상품, 패션/잡화
        0.06,  # 성동구 - 중가 상품, 생활용품
        0.05,  # 광진구 - 중가 상품, 생활용품
        0.05,  # 동대문구 - 저가 상품, 식품/간식
        0.04,  # 중랑구 - 저가 상품, 식품/간식
        0.05,  # 성북구 - 중가 상품, 생활용품
        0.04,  # 강북구 - 저가 상품, 식품/간식
        0.03,  # 도봉구 - 저가 상품, 식품/간식
        0.04,  # 노원구 - 중가 상품, 생활용품
        0.04,  # 은평구 - 중가 상품, 생활용품
        0.05,  # 서대문구 - 중가 상품, 생활용품
        0.06,  # 종로구 (시청, 명동) - 중가 상품, 생활용품
        0.07,  # 중구 (명동, 동대문) - 중가 상품, 생활용품
        0.06,  # 영등포구 (여의도) - 중가 상품, 생활용품
        0.05,  # 동작구 - 중가 상품, 생활용품
        0.04,  # 관악구 - 저가 상품, 식품/간식
    ]

    for user in user_profiles:
        # active 사용자는 집+회사 2개 가질 확률 높음
        num_spots = 1
        if (
            user["status"] == "active"
            and random.random() < ACTIVE_USER_TWO_SPOTS_PROBABILITY
        ):
            num_spots = 2

        for i in range(num_spots):
            # SEOUL_LOCATIONS에서 가중치 기반으로 지역 선택
            selected_location = random.choices(
                SEOUL_LOCATIONS, weights=location_weights
            )[0]
            center_lat, center_lon = selected_location[1]

            # 반경 0.5-2km 내 랜덤 좌표 생성 (인접 지역 탈출 방지)
            radius_km = random.uniform(0.5, 2.0)
            # km를 도 단위로 변환 (대략 1km = 0.009도)
            radius_deg = radius_km * 0.009

            # 랜덤 각도와 거리로 좌표 생성
            angle = random.uniform(0, 2 * 3.14159)
            distance = random.uniform(0, radius_deg)

            lat = center_lat + distance * math.cos(angle)
            lon = center_lon + distance * math.sin(angle)

            # 라벨 선택
            if i == 0:
                label = "집"
            else:
                label = random.choices(
                    ["회사", "자주가는곳", "카페"], weights=[0.6, 0.3, 0.1]
                )[0]

            wish_spot = {
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "label": label,
                "location": (lat, lon),  # (위도, 경도)
                "created_at": user["created_at"],
            }

            wish_spots.append(wish_spot)

    return wish_spots


def generate_mogu_posts(  # noqa: PLR0912, PLR0915
    num_posts: int = 5000, user_profiles: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """모구 게시물 생성 (현실적 분포 적용)"""
    posts = []

    for i in range(num_posts):
        # 카테고리 분포: 식품/간식류 45%, 생활용품 30%, 패션/잡화 15%, 뷰티/헬스케어 10%
        category = random.choices(
            ["식품/간식류", "생활용품", "패션/잡화", "뷰티/헬스케어"],
            weights=[0.45, 0.30, 0.15, 0.10],
        )[0]

        # 마켓 분포: 대형 마트 중심 + 현실적 분포 (대형마트 60%, 기타 40%)
        market_weights = [
            0.25,  # 코스트코 (대용량 구매 특화)
            0.20,  # 이마트 (대형 마트)
            0.15,  # 노브랜드 (대형 마트)
            0.10,  # 홈플러스 (대형 마트)
            0.08,  # 편의점 (소형 구매)
            0.08,  # 동네마켓 (지역 특화)
            0.07,  # 이커머스 (온라인)
            0.05,  # 전통시장 (지역 특화)
            0.02,  # 기타
        ]
        markets = [
            "코스트코",
            "이마트",
            "노브랜드",
            "홈플러스",
            "편의점",
            "동네마켓",
            "이커머스",
            "전통시장",
            "기타",
        ]
        mogu_market = random.choices(markets, weights=market_weights)[0]

        # 마켓별 특성을 반영한 가격 범위 (MARKET_CHARACTERISTICS 활용)
        market_info = MARKET_CHARACTERISTICS[mogu_market]
        market_price_range: tuple[int, int] = tuple(market_info["price_range"])  # type: ignore

        # 카테고리별 가격 범위 조정 (마켓 범위와 카테고리 범위 교집합)
        if category == "식품/간식류":
            min_price = max(market_price_range[0], 15000)
            max_price = min(market_price_range[1], 45000)
        elif category == "생활용품":
            min_price = max(market_price_range[0], 8000)
            max_price = min(market_price_range[1], 60000)
        elif category in ["패션/잡화", "뷰티/헬스케어"]:
            min_price = max(market_price_range[0], 10000)
            max_price = min(market_price_range[1], 70000)
        else:
            min_price = max(market_price_range[0], 10000)
            max_price = min(market_price_range[1], 50000)

        # 범위가 유효하지 않으면 마켓 범위 사용
        if min_price >= max_price:
            min_price = market_price_range[0]
            max_price = market_price_range[1]

        base_price = random.randint(min_price, max_price)

        # log1p 분포로 가격 생성 (양/음 변동 허용)
        multiplier = max(0.6, min(1.6, random.lognormvariate(0, 0.25)))
        price = int(base_price * multiplier)

        # 수고비 설정 (0-20%, 기본 0-10%가 다수, 15%+는 소수)
        labor_fee_ranges = [
            (0.00, 0.05, 0.15),  # 0-5%, 15% 확률
            (0.05, 0.10, 0.50),  # 5-10%, 50% 확률
            (0.10, 0.15, 0.25),  # 10-15%, 25% 확률
            (0.15, 0.20, 0.10),  # 15-20%, 10% 확률
        ]
        selected_range = random.choices(
            labor_fee_ranges, weights=[r[2] for r in labor_fee_ranges]
        )[0]
        labor_fee = max(
            100, int(price * random.uniform(selected_range[0], selected_range[1]))
        )

        # 목표 인원 설정 (마켓의 bulk_tendency 반영)
        is_bulk_market = bool(market_info["bulk_tendency"])  # 타입 캐스팅

        if category in ["식품/간식류", "생활용품"]:
            if is_bulk_market:
                # 대용량 마켓: 더 많은 인원 선호
                target_count_options = [
                    (4, 0.10),  # 4명, 10% 확률
                    (5, 0.25),  # 5명, 25% 확률
                    (6, 0.35),  # 6명, 35% 확률
                    (7, 0.20),  # 7명, 20% 확률
                    (8, 0.10),  # 8명, 10% 확률
                ]
            else:
                # 일반 마켓: 기존 분포 유지
                target_count_options = [
                    (3, 0.10),  # 3명, 10% 확률
                    (4, 0.30),  # 4명, 30% 확률
                    (5, 0.35),  # 5명, 35% 확률
                    (6, 0.20),  # 6명, 20% 확률
                    (7, 0.05),  # 7명, 5% 확률
                ]
        elif is_bulk_market:
            # 대용량 마켓이지만 패션/뷰티는 적당히
            target_count_options = [
                (3, 0.25),  # 3명, 25% 확률
                (4, 0.35),  # 4명, 35% 확률
                (5, 0.25),  # 5명, 25% 확률
                (6, 0.15),  # 6명, 15% 확률
            ]
        else:
            # 일반 마켓: 기존 분포 유지
            target_count_options = [
                (2, 0.20),  # 2명, 20% 확률
                (3, 0.30),  # 3명, 30% 확률
                (4, 0.25),  # 4명, 25% 확률
                (5, 0.15),  # 5명, 15% 확률
                (6, 0.10),  # 6명, 10% 확률
            ]

        target_count = random.choices(
            [opt[0] for opt in target_count_options],
            weights=[opt[1] for opt in target_count_options],
        )[0]

        # 상품명 생성
        product_name = random.choice(CATEGORY_PRODUCTS[category])
        title = f"{product_name} 모구 ({mogu_market})"

        # 위치 생성 (마켓 주변 또는 주최자 위시스팟 주변 0.3-1.5km)
        location = generate_random_location()

        # 모구 일시 생성 (발표일 보장 로직 포함)
        force_after_presentation = (
            i % int(1 / CFG.recruiting_quota_ratio) == 0
        )  # 20% 보장

        if force_after_presentation:
            # 발표일 이후 게시물 (recruiting 보장)
            days_after_presentation = random.randint(0, 3)
            base_datetime = PRESENTATION_DAY + timedelta(days=days_after_presentation)
        else:
            # 일반 게시물 (BASE_NOW~+14일)
            days_ahead = random.randint(0, 14)
            base_datetime = BASE_NOW + timedelta(days=days_ahead)

        # 시간대 분포: 평일 저녁(19-22) 40%, 주말 오전(9-12) 30%, 주말 오후(14-17) 30%
        # 야간 시간대도 포함 (0-1시, 23시) - 야간 근무자 고려
        if base_datetime.weekday() < WEEKDAY_THRESHOLD:  # 평일
            hour = random.choices(
                [19, 20, 21, 22, 23, 0, 1],
                weights=[0.15, 0.20, 0.20, 0.15, 0.10, 0.10, 0.10],
            )[0]
        else:  # 주말
            hour = random.choices(
                [9, 10, 11, 12, 14, 15, 16, 17, 22, 23, 0, 1],
                weights=[
                    0.12,
                    0.12,
                    0.12,
                    0.12,
                    0.12,
                    0.12,
                    0.12,
                    0.12,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                ],
            )[0]

        mogu_datetime = base_datetime.replace(
            hour=hour, minute=random.randint(0, 59), second=0, microsecond=0
        )

        # 작성자 선택 (active 사용자 우선)
        if user_profiles:
            active_users = [u for u in user_profiles if u["status"] == "active"]
            if active_users and random.random() < ACTIVE_USER_PROBABILITY:
                author = random.choice(active_users)
            else:
                author = random.choice(user_profiles)
            user_id = author["id"]
        else:
            user_id = str(uuid.uuid4())

        # 추천 시스템용 상태 분포: recruiting 대폭 증가
        if force_after_presentation:
            # 발표일 이후 게시물은 반드시 recruiting 상태
            status = "recruiting"
            joined_count = random.randint(0, target_count - 1)  # 목표 인원 미만
        else:
            status = random.choices(
                ["recruiting", "locked", "purchasing", "distributing", "completed"],
                weights=[0.85, 0.08, 0.04, 0.02, 0.01],  # recruiting 85%로 대폭 증가
            )[0]

            # joined_count는 시간 경과와 인기와 양의 상관
            max_joined = target_count - 1 if status == "recruiting" else target_count
            if status == "recruiting":
                # recruiting 상태에서는 0~target-1
                joined_count = random.randint(0, max_joined)
            else:
                # 다른 상태에서는 target에 가까운 값
                joined_count = random.randint(max(0, target_count - 2), target_count)

        post = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": title,
            "description": f"{product_name}을(를) {mogu_market}에서 함께 구매하실 분을 찾습니다!",
            "price": price,
            "labor_fee": labor_fee,
            "category": category,
            "mogu_market": mogu_market,
            "mogu_spot": location,
            "mogu_datetime": mogu_datetime,
            "status": status,
            "target_count": target_count,
            "joined_count": joined_count,
            "created_at": generate_realistic_datetime(60),
        }

        posts.append(post)

    return posts


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간의 거리 계산 (km) - Haversine 공식 사용"""
    # Haversine 공식 사용
    R = 6371  # 지구 반지름 (km)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
        math.radians(lat1)
    ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_distance_cached(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    cache: dict[tuple[tuple[float, float], ...], float],
) -> float:
    """캐싱을 사용한 거리 계산 (km) - 키 정규화 포함"""

    # 좌표 정규화 (소수점 5자리로 반올림, ≈1m 정밀도)
    def _quantize(x: float) -> float:
        return round(x, CFG.cache_precision_digits)

    # 캐시 키 생성 (정규화된 정렬된 좌표 쌍)
    key = tuple(
        sorted([(_quantize(lat1), _quantize(lon1)), (_quantize(lat2), _quantize(lon2))])
    )

    if key in cache:
        return cache[key]

    distance = calculate_distance(lat1, lon1, lat2, lon2)
    cache[key] = distance
    return distance


def generate_user_interactions(  # noqa: PLR0912, PLR0915
    user_profiles: list[dict[str, Any]],
    mogu_posts: list[dict[str, Any]],
    wish_spots: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """사용자 상호작용 생성 (거리/시간대/관심사 상관관계 반영)"""
    favorites: list[dict[str, Any]] = []
    participations: list[dict[str, Any]] = []
    ratings: list[dict[str, Any]] = []

    # 거리 계산 캐시 (성능 최적화)
    distance_cache: dict[tuple[tuple[float, float], ...], float] = {}

    # 참여자 수 O(1) 카운터 (성능 최적화)
    participants_count: dict[str, int] = defaultdict(int)

    # 사용자별 위시스팟 매핑
    user_wish_spots: dict[str, list[dict[str, Any]]] = {}
    for spot in wish_spots:
        if spot["user_id"] not in user_wish_spots:
            user_wish_spots[spot["user_id"]] = []
        user_wish_spots[spot["user_id"]].append(spot)

    # 각 사용자별로 상호작용 생성
    for user in user_profiles:
        if user["status"] != "active":
            continue

        # 사용자의 위시스팟 위치들
        user_spots = user_wish_spots.get(user["id"], [])
        if not user_spots:
            continue

        # 사용자 선호도 점수 계산 함수
        def calculate_preference_score(post: dict[str, Any]) -> float:
            score = 0.0

            # 1. 카테고리 일치 (+0.8)
            if post["category"] in user["interested_categories"]:
                score += 0.8

            # 2. 위시마켓 일치 (+0.6)
            if post["mogu_market"] in user["wish_markets"]:
                score += 0.6

            # 3. 거리 계산 (가장 가까운 위시스팟 기준, 캐시 사용)
            min_distance = float("inf")
            for spot in user_spots:
                spot_lat, spot_lon = spot["location"]
                post_lat, post_lon = post["mogu_spot"]
                distance = calculate_distance_cached(
                    spot_lat, spot_lon, post_lat, post_lon, distance_cache
                )
                min_distance = min(min_distance, distance)

            # 거리별 점수 (exp(-d/α) 공식 사용, α=4.0km)
            alpha = 4.0  # 거리 감쇠 계수 (km) - 3km 이내에서 점수 차이 최소화
            distance_score = math.exp(-min_distance / alpha)
            score += distance_score

            # 4. 선호 시간대 일치 (+0.5)
            post_hour = post["mogu_datetime"].hour
            if user["wish_times"][post_hour] == 1:
                score += 0.5

            # 5. 가격 합리성 (카테고리별 중앙값 기준)
            if post["category"] == "식품/간식류":
                reasonable_range = (15000, 45000)
            elif post["category"] == "생활용품":
                reasonable_range = (8000, 60000)
            else:
                reasonable_range = (10000, 70000)

            if reasonable_range[0] <= post["price"] <= reasonable_range[1]:
                score += 0.3
            elif post["price"] > reasonable_range[1] * 1.5:  # 너무 비쌈
                score -= 0.5
            elif post["price"] < reasonable_range[0] * 0.5:  # 너무 저렴 (사기 느낌)
                score -= 0.2

            # 6. 신선도 (등록 24시간 이내 +0.3)
            hours_since_creation = (
                BASE_NOW - post["created_at"]
            ).total_seconds() / 3600
            if hours_since_creation <= FRESHNESS_HOURS:
                score += 0.3

            return score

        # 사용자별 상호작용 수 결정 (페르소나별 명확한 기준)
        # 모구장과 모구러 역할을 모두 고려한 하이브리드 활동성
        # 추천 시스템을 위한 대폭 증가된 상호작용 수
        persona_base_interactions = {
            "P1_OfficeWorker_Gangnam": 80,  # 직장인: 추천 학습용 충분한 활동
            "P2_Family_Costco_Suwon": 100,  # 가족: 가장 활발한 활동
            "P3_Fashion_Beauty_Hongdae": 70,  # 패션/뷰티: 관심사 기반 활동
            "P4_NightShifter_Incheon": 60,  # 야간근무자: 제한적 활동
            "P5_Student_Sindorim": 75,  # 학생: 적당한 활동
        }

        # 추천 시스템용 기본 상호작용 수 (대폭 증가)
        base_interactions = 80  # 기본값 (기존 20에서 4배 증가)
        for persona_key, interaction_count in persona_base_interactions.items():
            if persona_key in user["nickname"]:
                base_interactions = interaction_count
                break

        # 가구수 보정 (기존보다 약한 영향)
        household_multiplier = {"1인": 1.0, "2인": 1.1, "3인": 1.2, "4인 이상": 1.3}
        base_interactions = int(
            base_interactions * household_multiplier.get(user["household_size"], 1.0)
        )

        # Power User는 2-3배 더 많은 상호작용 (기존보다 약한 영향)
        if user.get("is_power_user", False):
            power_multiplier = random.uniform(2.0, 3.0)
            base_interactions = int(base_interactions * power_multiplier)

        # Power User는 더 다양한 카테고리와 마켓에서 활동
        if user.get("is_power_user", False):
            # Power User는 관심카테고리를 확장
            if len(user["interested_categories"]) < MAX_CATEGORIES:
                additional_categories = [
                    cat
                    for cat in ["식품/간식류", "생활용품", "패션/잡화", "뷰티/헬스케어"]
                    if cat not in user["interested_categories"]
                ]
                if additional_categories:
                    user["interested_categories"].extend(
                        random.sample(
                            additional_categories, min(2, len(additional_categories))
                        )
                    )

            # Power User는 더 많은 마켓에서 활동
            if len(user["wish_markets"]) < MAX_MARKETS:
                additional_markets = [
                    market
                    for market in [
                        "코스트코",
                        "이마트",
                        "노브랜드",
                        "홈플러스",
                        "편의점",
                        "동네마켓",
                        "이커머스",
                        "전통시장",
                    ]
                    if market not in user["wish_markets"]
                ]
                if additional_markets:
                    user["wish_markets"].extend(
                        random.sample(
                            additional_markets, min(2, len(additional_markets))
                        )
                    )

        # Top-K 후보 필터링 (성능 최적화)
        # 1단계: 관심 카테고리/마켓 일치 후보
        category_market_candidates = [
            post
            for post in mogu_posts
            if post["status"] == "recruiting"
            and post["category"] in user["interested_categories"]
            and post["mogu_market"] in user["wish_markets"]
        ]

        # 2단계: 거리 기반 후보 (6km 이내)
        def is_within_distance(post: dict[str, Any], max_distance: float = 6.0) -> bool:
            """게시물이 사용자 위시스팟으로부터 지정된 거리 이내인지 확인"""
            post_lat, post_lon = post["mogu_spot"]
            min_distance = float("inf")
            for spot in user_spots:
                spot_lat, spot_lon = spot["location"]
                distance = calculate_distance_cached(
                    spot_lat, spot_lon, post_lat, post_lon, distance_cache
                )
                min_distance = min(min_distance, distance)
            return min_distance <= max_distance

        distance_candidates = [
            post
            for post in mogu_posts
            if post["status"] == "recruiting" and is_within_distance(post, 6.0)
        ]

        # 3단계: 후보군 통합 및 중복 제거 (ID 기반)
        all_candidates = category_market_candidates + distance_candidates
        seen_ids = set()
        unique_candidates = []
        for candidate in all_candidates:
            if candidate["id"] not in seen_ids:
                seen_ids.add(candidate["id"])
                unique_candidates.append(candidate)
        all_candidates = unique_candidates

        # 4단계: 후보가 너무 적으면 추가 보완 (로깅 포함)
        if len(all_candidates) < MIN_CANDIDATES_THRESHOLD:
            logging.info(
                "Candidate shortage for user %s: %d < %d; adding time-matched posts",
                user["id"],
                len(all_candidates),
                MIN_CANDIDATES_THRESHOLD,
            )
            # 시간대 일치 후보 추가
            time_candidates = [
                post
                for post in mogu_posts
                if post["status"] == "recruiting"
                and user["wish_times"][post["mogu_datetime"].hour] == 1
            ]
            # 시간대 후보도 ID 기반으로 중복 제거
            for candidate in time_candidates:
                if candidate["id"] not in seen_ids:
                    seen_ids.add(candidate["id"])
                    all_candidates.append(candidate)

        # 5단계: 최대 K개 후보로 제한 (성능 최적화)
        final_candidates = (
            random.sample(
                all_candidates, min(CFG.max_candidates_k, len(all_candidates))
            )
            if len(all_candidates) > CFG.max_candidates_k
            else all_candidates
        )

        # 게시물별 선호도 점수 계산 (Top-K 후보만)
        post_scores = []
        for post in final_candidates:
            score = calculate_preference_score(post)
            post_scores.append((post, score))

        # heapq.nlargest로 상위 N개만 선택 (정렬 최적화)
        top_n = min(base_interactions, len(post_scores))
        top_scores = heapq.nlargest(top_n, post_scores, key=lambda x: x[1])

        num_interactions = len(top_scores)

        # 페르소나별 최소 참여 수 보장
        min_interactions = 0
        if "P1_OfficeWorker_Gangnam" in user["nickname"]:
            min_interactions = 5  # 직장인 최소 5개
        elif "P2_Family_Costco_Suwon" in user["nickname"]:
            min_interactions = 5  # 가족 최소 5개
        elif "P3_Fashion_Beauty_Hongdae" in user["nickname"]:
            min_interactions = 4  # 패션/뷰티 최소 4개
        elif "P4_NightShifter_Incheon" in user["nickname"]:
            min_interactions = 3  # 야간 근무자 최소 3개
        elif "P5_Student_Sindorim" in user["nickname"]:
            min_interactions = 3  # 학생 최소 3개

        num_interactions = max(num_interactions, min_interactions)

        for i in range(num_interactions):
            post, score = top_scores[i]

            # 페르소나 기반 가중치 적용
            weight = 1.0

            # 페르소나별 특별한 가중치 (우선 적용)
            if "P1_OfficeWorker_Gangnam" in user["nickname"]:
                # 직장인: 식품/간식류, 생활용품 선호
                if post["category"] in ["식품/간식류", "생활용품"]:
                    weight *= 3.0
                if post["mogu_market"] in ["코스트코", "이마트", "노브랜드"]:
                    weight *= 2.0
            elif "P2_Family_Costco_Suwon" in user["nickname"]:
                # 가족: 생활용품, 식품/간식류 선호
                if post["category"] in ["생활용품", "식품/간식류"]:
                    weight *= 4.0
                if post["mogu_market"] in ["코스트코", "이마트", "홈플러스"]:
                    weight *= 3.0
            elif "P3_Fashion_Beauty_Hongdae" in user["nickname"]:
                # 패션/뷰티: 패션/잡화, 뷰티/헬스케어 선호 (가중치 강화)
                if post["category"] in ["패션/잡화", "뷰티/헬스케어"]:
                    weight *= 8.0  # 매우 높은 선호도 (5.0 → 8.0)
                if post["mogu_market"] in ["이커머스", "동네마켓", "전통시장"]:
                    weight *= 4.0  # 마켓 선호도 강화 (2.5 → 4.0)
            elif "P4_NightShifter_Incheon" in user["nickname"]:
                # 야간 근무자: 생활용품 선호
                if post["category"] == "생활용품":
                    weight *= 3.0
                if post["mogu_market"] in ["노브랜드", "이마트", "전통시장"]:
                    weight *= 2.0
            elif "P5_Student_Sindorim" in user["nickname"]:
                # 학생: 식품/간식류, 패션/잡화 선호 (더 강한 가중치)
                if post["category"] in ["식품/간식류", "패션/잡화"]:
                    weight *= 6.0  # 매우 강한 선호도
                if post["mogu_market"] in ["노브랜드", "이마트", "동네마켓"]:
                    weight *= 4.0  # 매우 강한 마켓 선호도
                # 학생은 가격에 매우 민감하므로 개인 부담 금액 기준으로 판단
                personal_cost = post["price"] / (
                    post["target_count"] + 1
                )  # 개인 부담 금액
                if personal_cost < STUDENT_COST_THRESHOLDS["very_low"]:
                    weight *= 5.0  # 매우 강한 가격 선호도
                elif personal_cost < STUDENT_COST_THRESHOLDS["low"]:
                    weight *= 4.0  # 매우 강한 가격 선호도
                elif personal_cost < STUDENT_COST_THRESHOLDS["medium"]:
                    weight *= 3.0
                elif personal_cost < STUDENT_COST_THRESHOLDS["high"]:
                    weight *= 2.0
                # 학생은 다른 마켓도 참여 가능 (단, 가중치는 낮게)
                if post["mogu_market"] not in ["노브랜드", "이마트", "동네마켓"]:
                    weight *= 0.8  # 다른 마켓은 가중치 감소

            # 성별 기반 가중치
            if post["category"] == "뷰티/헬스케어":
                if user["gender"] == "female":
                    weight *= 4.0  # 여성 4배
                else:
                    weight *= 0.5  # 남성 0.5배
            elif post["category"] == "패션/잡화":
                if user["gender"] == "female":
                    weight *= 1.5  # 여성 1.5배
                else:
                    weight *= 0.8  # 남성 0.8배

            # 연령대 기반 가중치 (birth_date로 계산)
            current_year = BASE_NOW.year
            age = current_year - user["birth_date"].year

            if post["category"] == "패션/잡화":
                if (
                    AGE_THRESHOLDS["young_adult_start"]
                    <= age
                    < AGE_THRESHOLDS["young_adult_end"]
                ):
                    weight *= 3.0  # 20대 3배
                elif age >= AGE_THRESHOLDS["middle_aged"]:
                    weight *= 0.5  # 40대 이상 0.5배
            elif post["category"] == "뷰티/헬스케어":
                if (
                    AGE_THRESHOLDS["young_adult_start"]
                    <= age
                    < AGE_THRESHOLDS["young_adult_end"]
                ):
                    weight *= 2.0  # 20대 2배
                elif age >= AGE_THRESHOLDS["middle_aged"]:
                    weight *= 0.7  # 40대 이상 0.7배

            # 가구수 기반 가중치
            if post["category"] == "생활용품":
                if user["household_size"] == "3인":
                    weight *= 1.5  # 3인 가구 1.5배
                elif user["household_size"] == "4인 이상":
                    weight *= 2.0  # 4인 이상 가구 2배
            elif post["category"] == "식품/간식류":
                if user["household_size"] == "3인":
                    weight *= 1.3  # 3인 가구 1.3배
                elif user["household_size"] == "4인 이상":
                    weight *= 1.8  # 4인 이상 가구 1.8배

            # 가중치 포화 방지 (클립)
            weight = min(weight, 10.0)

            # 로지스틱 스코어를 확률로 변환 (가중치 적용)
            probability = 1 / (1 + math.exp(-score * weight))

            # 노이즈 추가 (10-20%는 규칙을 벗어난 행동)
            if random.random() < NOISE_PROBABILITY:
                probability = random.random()

            # 찜하기 확률 (페르소나별 명확한 기준)
            persona_favorite_multiplier = {
                "P1_OfficeWorker_Gangnam": 1.5,  # 직장인: 적당한 찜하기
                "P2_Family_Costco_Suwon": 2.0,  # 가족: 활발한 찜하기
                "P3_Fashion_Beauty_Hongdae": 2.5,  # 패션/뷰티: 가장 활발한 찜하기
                "P4_NightShifter_Incheon": 1.0,  # 야간근무자: 기본 찜하기
                "P5_Student_Sindorim": 1.8,  # 학생: 적극적 찜하기
            }

            favorite_multiplier = 1.0
            for persona_key, multiplier in persona_favorite_multiplier.items():
                if persona_key in user["nickname"]:
                    favorite_multiplier = multiplier
                    break

            # 추천 시스템용 찜하기 확률 대폭 증가
            favorite_prob = min(probability * 0.3 * favorite_multiplier, 0.25)

            if random.random() < favorite_prob:
                # 실제 상호작용 시간 생성 (선호시간대와 70% 일치, 30%는 다른 시간대)
                if (
                    random.random() < TIME_MATCH_PROBABILITY
                    and user["wish_times"][post["mogu_datetime"].hour] == 1
                ):
                    # 선호시간대와 일치하는 경우
                    interaction_time = post["mogu_datetime"]
                else:
                    # 다른 시간대 (현실적인 변동성)
                    interaction_time = generate_realistic_datetime(90)

                # 게시물 생성 이후로 클램프
                interaction_time = clamp_after(interaction_time, post["created_at"])

                favorite = {
                    "user_id": user["id"],
                    "mogu_post_id": post["id"],
                    "created_at": interaction_time,
                }
                favorites.append(favorite)

            # 참여 확률 (페르소나별 명확한 기준)
            persona_participation_multiplier = {
                "P1_OfficeWorker_Gangnam": 1.2,  # 직장인: 기본 참여
                "P2_Family_Costco_Suwon": 2.0,  # 가족: 활발한 참여
                "P3_Fashion_Beauty_Hongdae": 1.5,  # 패션/뷰티: 적당한 참여
                "P4_NightShifter_Incheon": 1.0,  # 야간근무자: 기본 참여
                "P5_Student_Sindorim": 1.8,  # 학생: 적극적 참여
            }

            participation_multiplier = 1.0
            for persona_key, multiplier in persona_participation_multiplier.items():
                if persona_key in user["nickname"]:
                    participation_multiplier = multiplier
                    break

            # 추천 시스템용 참여 확률 대폭 증가
            participation_prob = min(probability * 0.4 * participation_multiplier, 0.30)

            # 모구 인원 체킹: 자리가 있을 때만 참여 가능 (O(1) 카운터 사용)
            current_participants = participants_count[post["id"]]

            # 발표일 이후 일정은 항상 한 자리 남기기 (데모용 recruiting 보장)
            if post["mogu_datetime"] >= PRESENTATION_DAY and current_participants >= (
                post["target_count"] - 1
            ):
                continue

            # 목표 인원에 도달했으면 참여 불가
            if current_participants >= post["target_count"]:
                continue

            if random.random() < participation_prob:
                # 참여 상태 분포: applied 100% 생성 후 일부만 accepted/fulfilled
                status = "applied"
                if random.random() < ACCEPTED_PROBABILITY:
                    status = "accepted"
                    if random.random() < FULFILLED_PROBABILITY:
                        status = "fulfilled"
                elif random.random() < REJECTED_PROBABILITY:
                    status = "rejected"
                elif random.random() < CANCELED_PROBABILITY:
                    status = "canceled"
                elif random.random() < NO_SHOW_PROBABILITY:
                    status = "no_show"

                # 참여 시간도 선호시간대와 70% 일치, 30%는 다른 시간대
                if (
                    random.random() < TIME_MATCH_PROBABILITY
                    and user["wish_times"][post["mogu_datetime"].hour] == 1
                ):
                    # 선호시간대와 일치하는 경우
                    applied_time = post["mogu_datetime"]
                else:
                    # 다른 시간대 (현실적인 변동성)
                    applied_time = generate_realistic_datetime(90)

                # 게시물 생성 이후로 클램프
                applied_time = clamp_after(applied_time, post["created_at"])

                # 시간 순서 보장: applied_at → decided_at
                decided_time = None
                if status != "applied":
                    # 5분~48시간 후에 결정
                    decided_time = after_time(applied_time, 5, 48 * 60)

                participation = {
                    "user_id": user["id"],
                    "mogu_post_id": post["id"],
                    "status": status,
                    "applied_at": applied_time,
                    "decided_at": decided_time,
                }
                participations.append(participation)

                # 참여자 수 카운터 업데이트 (O(1))
                if status in {"applied", "accepted", "fulfilled"}:
                    participants_count[post["id"]] += 1

                # fulfilled인 경우 평가 생성 (자기자신 리뷰 방지)
                if (
                    status == "fulfilled"
                    and random.random() < RATING_PROBABILITY
                    and user["id"] != post["user_id"]  # 자기자신 리뷰 방지
                ):
                    # 별점 분포: 평균 4.2±0.6 (정규분포 절단)
                    rating_score = random.gauss(4.2, 0.6)
                    rating_score = max(1, min(5, int(round(rating_score))))

                    # 키워드 생성 (positive:negative ≈ 7:3)
                    positive_keywords = [
                        "friendly_communication",
                        "punctual",
                        "reliable",
                        "good_condition",
                        "fast_delivery",
                        "helpful",
                        "clean",
                        "organized",
                    ]
                    negative_keywords = [
                        "late",
                        "poor_communication",
                        "damaged",
                        "unreliable",
                        "rude",
                        "messy",
                    ]

                    if rating_score >= RATING_THRESHOLD_HIGH:
                        keywords = random.sample(
                            positive_keywords, random.randint(1, 3)
                        )
                    elif rating_score <= RATING_THRESHOLD_LOW:
                        keywords = random.sample(
                            negative_keywords, random.randint(1, 2)
                        )
                    else:
                        keywords = random.sample(
                            positive_keywords + negative_keywords, random.randint(1, 2)
                        )

                    # 시간 순서 보장: max(decided_at, mogu_datetime) → rating_at
                    rating_base_time = max(
                        decided_time or applied_time, post["mogu_datetime"]
                    )
                    rating_time = after_time(
                        rating_base_time, 10, 24 * 60
                    )  # 10분~24시간 후

                    # 게시물 생성 이후로 클램프
                    rating_time = clamp_after(rating_time, post["created_at"])

                    rating = {
                        "id": str(uuid.uuid4()),
                        "mogu_post_id": post["id"],
                        "reviewer_id": user["id"],
                        "reviewee_id": post["user_id"],
                        "stars": rating_score,
                        "keywords": keywords,
                        "created_at": rating_time,
                    }
                    ratings.append(rating)

    # 참여 생성 후 joined_count 및 상태 업데이트 (상태 머신 로직)
    print("🔄 joined_count 및 상태 업데이트 중...")
    for post in mogu_posts:
        # 해당 게시물의 실제 참여자 수 계산
        actual_participants = len(
            [
                p
                for p in participations
                if p["mogu_post_id"] == post["id"]
                and p["status"] in ["applied", "accepted", "fulfilled"]
            ]
        )

        # joined_count를 실제 참여자 수로 업데이트
        post["joined_count"] = actual_participants

        # fulfilled 참여자 수 계산
        fulfilled_participants = len(
            [
                p
                for p in participations
                if p["mogu_post_id"] == post["id"] and p["status"] == "fulfilled"
            ]
        )

        # 상태 머신 로직 (발표일 보장 포함)
        if post["mogu_datetime"] >= PRESENTATION_DAY:
            # 발표일 이후 게시물은 recruiting 상태 유지
            post["status"] = "recruiting"
        elif fulfilled_participants > 0:
            # fulfilled 참여자가 있으면 completed 상태
            post["status"] = "completed"
        elif (
            fulfilled_participants == 0 and actual_participants >= post["target_count"]
        ):
            # 목표 인원 도달했지만 fulfilled 없으면 locked 상태
            post["status"] = "locked"
        elif (
            post["status"] == "recruiting"
            and actual_participants < post["target_count"]
        ):
            # 여전히 모집 중
            post["status"] = "recruiting"
        # 다른 상태들은 그대로 유지

    return favorites, participations, ratings


def generate_comments(
    mogu_posts: list[dict[str, Any]], participations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """댓글 데이터 생성 (참여자 중 20-35%가 댓글 작성)"""
    comments = []

    # 참여자별 게시물 매핑
    post_participants: dict[str, list[str]] = {}
    for participation in participations:
        if participation["status"] in ["applied", "accepted", "fulfilled"]:
            post_id = participation["mogu_post_id"]
            if post_id not in post_participants:
                post_participants[post_id] = []
            post_participants[post_id].append(participation["user_id"])

    # 각 게시물별로 댓글 생성 (상태 업데이트 전 스냅샷 기준)
    for post in mogu_posts:
        # recruiting 또는 locked 상태에서 댓글 허용 (모집 중이거나 모집 완료된 상태)
        if post["status"] not in ["recruiting", "locked"]:
            continue

        participants = post_participants.get(post["id"], [])
        if not participants:
            continue

        # 참여자 중 20-35%가 댓글 작성
        comment_rate = random.uniform(0.20, 0.35)
        num_comments = max(1, int(len(participants) * comment_rate))

        # 댓글 내용 생성
        comment_templates = [
            "수고비는 어떻게 받으시나요?",
            "언제쯤 수령 가능한가요?",
            "분배는 어떻게 하실 예정인가요?",
            "혹시 다른 옵션도 있나요?",
            "참여하고 싶습니다!",
            "언제까지 신청 받으시나요?",
            "수령 장소는 어디인가요?",
            "혹시 취소 가능한가요?",
        ]

        # 댓글 중복/스팸 완화를 위한 캐시
        used_comments = set()

        for i in range(num_comments):
            # 중복 방지: 최대 5번 시도
            for attempt in range(5):
                commenter = random.choice(participants)
                content = random.choice(comment_templates)
                comment_key = (commenter, content)

                if comment_key not in used_comments:
                    used_comments.add(comment_key)
                    break
            else:
                # 5번 시도 후에도 중복이면 그냥 진행 (극히 드문 경우)
                commenter = random.choice(participants)
                content = random.choice(comment_templates)

            # 댓글 시간: 게시물 생성 후 ~ 모구 일시 전까지
            comment_time = generate_realistic_datetime(90)
            comment_time = clamp_after(comment_time, post["created_at"])
            if comment_time > post["mogu_datetime"]:
                # 모구 일시보다 늦으면 모구 일시 1시간 전으로 조정
                comment_time = post["mogu_datetime"] - timedelta(hours=1)

            comment = {
                "id": str(uuid.uuid4()),
                "mogu_post_id": post["id"],
                "user_id": commenter,
                "content": content,
                "created_at": comment_time,
            }
            comments.append(comment)

    return comments


async def main(seed: int = 42) -> None:
    """메인 실행 함수"""
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # 재현 가능성을 위한 seed 설정
    random.seed(seed)
    print(f"🚀 모구 AI 추천 시스템 더미 데이터 생성 시작... (seed: {seed})")

    # 1. 사용자 프로필 생성 (1000명)
    print("📊 사용자 프로필 생성 중...")
    user_profiles = generate_user_profiles(1000)
    print(f"✅ {len(user_profiles)}명의 사용자 프로필 생성 완료")

    # 2. 위시스팟 생성 (1400-1800개)
    print("📍 위시스팟 생성 중...")
    wish_spots = generate_user_wish_spots(user_profiles)
    print(f"✅ {len(wish_spots)}개의 위시스팟 생성 완료")

    # 3. 모구 게시물 생성 (5000개)
    print("📝 모구 게시물 생성 중...")
    mogu_posts = generate_mogu_posts(5000, user_profiles)
    print(f"✅ {len(mogu_posts)}개의 모구 게시물 생성 완료")

    # 4. 사용자 상호작용 생성 (거리/시간대/관심사 상관관계 반영)
    print("🔄 사용자 상호작용 생성 중...")
    favorites, participations, ratings = generate_user_interactions(
        user_profiles, mogu_posts, wish_spots
    )
    print(
        f"✅ 찜하기: {len(favorites)}개, 참여: {len(participations)}개, 평가: {len(ratings)}개"
    )

    # 5. 댓글 생성
    print("💬 댓글 생성 중...")
    comments = generate_comments(mogu_posts, participations)
    print(f"✅ {len(comments)}개의 댓글 생성 완료")

    # 6. 가격 분포 통계 출력
    summarize_prices(mogu_posts)

    # 7. 발표일 이후 규칙 검증 (어서션)
    print("🔍 발표일 이후 규칙 검증 중...")
    for post in mogu_posts:
        if post["mogu_datetime"] >= PRESENTATION_DAY:
            assert post["joined_count"] <= post["target_count"] - 1, (
                f"Post {post['id']} overfilled after presentation day"
            )
            assert post["status"] == "recruiting", (
                f"Post {post['id']} not recruiting after presentation day"
            )
    print("✅ 발표일 이후 규칙 검증 완료")

    # 8. 데이터 저장
    print("💾 데이터 저장 중...")
    dummy_data: dict[str, Any] = {
        "users": user_profiles,
        "wish_spots": wish_spots,
        "mogu_posts": mogu_posts,
        "favorites": favorites,
        "participations": participations,
        "ratings": ratings,
        "comments": comments,
        "generated_at": BASE_NOW.isoformat(),
        "statistics": {
            "total_users": len(user_profiles),
            "total_wish_spots": len(wish_spots),
            "total_posts": len(mogu_posts),
            "total_favorites": len(favorites),
            "total_participations": len(participations),
            "total_ratings": len(ratings),
            "total_comments": len(comments),
            "participation_status": {
                "applied": len([p for p in participations if p["status"] == "applied"]),
                "accepted": len(
                    [p for p in participations if p["status"] == "accepted"]
                ),
                "fulfilled": len(
                    [p for p in participations if p["status"] == "fulfilled"]
                ),
                "rejected": len(
                    [p for p in participations if p["status"] == "rejected"]
                ),
                "canceled": len(
                    [p for p in participations if p["status"] == "canceled"]
                ),
                "no_show": len([p for p in participations if p["status"] == "no_show"]),
            },
        },
    }

    # JSON 파일로 저장 (gzip 압축)
    with gzip.open("dummy_data.json.gz", "wt", encoding="utf-8") as f:
        json.dump(
            dummy_data,
            f,
            ensure_ascii=False,
            indent=None,
            separators=(",", ":"),
            default=str,
        )

    print("🎉 더미 데이터 생성 완료!")
    print("📁 파일 저장: dummy_data.json.gz")
    print("📊 통계:")
    print(f"   - 사용자: {dummy_data['statistics']['total_users']}명")
    print(f"   - 위시스팟: {dummy_data['statistics']['total_wish_spots']}개")
    print(f"   - 게시물: {dummy_data['statistics']['total_posts']}개")
    print(f"   - 찜하기: {dummy_data['statistics']['total_favorites']}개")
    print(f"   - 참여: {dummy_data['statistics']['total_participations']}개")
    print(f"   - 평가: {dummy_data['statistics']['total_ratings']}개")
    print(f"   - 댓글: {dummy_data['statistics']['total_comments']}개")

    # 페르소나별 통계 출력
    print("\n👥 페르소나별 통계:")
    for persona in PERSONAS:
        persona_users: list[dict[str, Any]] = [
            u for u in user_profiles if persona["nickname"] in u["nickname"]
        ]
        persona_favorites: list[dict[str, Any]] = [
            f for f in favorites if any(u["id"] == f["user_id"] for u in persona_users)
        ]
        persona_participations: list[dict[str, Any]] = [
            p
            for p in participations
            if any(u["id"] == p["user_id"] for u in persona_users)
        ]
        print(
            f"   - {persona['nickname']}: {len(persona_users)}명, 찜하기: {len(persona_favorites)}개, 참여: {len(persona_participations)}개"
        )


if __name__ == "__main__":
    import sys

    # 명령행 인자로 seed 받기 (기본값: 42)
    seed = 42
    if len(sys.argv) > 1:
        try:
            seed = int(sys.argv[1])
        except ValueError:
            print("⚠️  잘못된 seed 값입니다. 기본값 42를 사용합니다.")

    asyncio.run(main(seed))
