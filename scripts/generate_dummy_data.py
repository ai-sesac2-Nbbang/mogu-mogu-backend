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
import json
import math
import random
import uuid
from datetime import date, datetime, timedelta
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
    """현실적인 날짜/시간 생성"""
    now = datetime.now()
    random_days = random.randint(0, days_back)
    random_hours = random.randint(0, 23)
    random_minutes = random.randint(0, 59)

    return now - timedelta(days=random_days, hours=random_hours, minutes=random_minutes)


def generate_user_profiles(num_users: int = 1000) -> list[dict[str, Any]]:
    """사용자 프로필 생성 (현실적 분포 적용)"""
    profiles = []

    # 페르소나 5명 고정 (회귀 테스트용)
    persona_profiles = []
    for persona in PERSONAS:
        profile = persona.copy()
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
        interested_categories = list(set(interested_categories))  # 중복 제거

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
        wish_markets = list(set(wish_markets))

        # 선호 시간대: 3-6개 시간대 선택, 평일 저녁(19-22)과 주말 오전/오후 비중 높게
        wish_times = [0] * 24
        num_time_slots = random.randint(3, 6)

        # 평일 저녁 시간대 (19-22) 높은 확률
        evening_slots = [19, 20, 21, 22]
        for slot in evening_slots:
            if random.random() < EVENING_PROBABILITY:
                wish_times[slot] = 1
                num_time_slots -= 1

        # 주말 오전/오후 시간대 (9-12, 14-17) 중간 확률
        weekend_slots = [9, 10, 11, 12, 14, 15, 16, 17]
        for slot in weekend_slots:
            if num_time_slots <= 0:
                break
            if random.random() < WEEKEND_PROBABILITY:
                wish_times[slot] = 1
                num_time_slots -= 1

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


def generate_mogu_posts(  # noqa: PLR0912
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

        # 카테고리별 합리적 가격 범위 (log1p 분포 활용)
        if category == "식품/간식류":
            base_price = random.randint(15000, 45000)
        elif category == "생활용품":
            base_price = random.randint(8000, 60000)
        elif category in ["패션/잡화", "뷰티/헬스케어"]:
            base_price = random.randint(10000, 70000)
        else:
            base_price = random.randint(10000, 50000)

        # log1p 분포로 가격 생성 (더 현실적)
        price = int(base_price * (1 + random.lognormvariate(0, 0.3)))

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
        labor_fee = int(price * random.uniform(selected_range[0], selected_range[1]))

        # 목표 인원 설정 (3-8명, 식품/생활용 4-6 모드)
        if category in ["식품/간식류", "생활용품"]:
            target_count_options = [
                (3, 0.10),  # 3명, 10% 확률
                (4, 0.30),  # 4명, 30% 확률
                (5, 0.35),  # 5명, 35% 확률
                (6, 0.20),  # 6명, 20% 확률
                (7, 0.05),  # 7명, 5% 확률
            ]
        else:
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

        # 모구 일시 생성 (오늘~+14일, 평일 저녁과 주말 오전/오후 비중 높게)
        days_ahead = random.randint(0, 14)
        base_datetime = datetime.now() + timedelta(days=days_ahead)

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
    """두 좌표 간의 거리 계산 (km)"""
    # Haversine 공식 사용
    R = 6371  # 지구 반지름 (km)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
        math.radians(lat1)
    ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def generate_user_interactions(  # noqa: PLR0912, PLR0915
    user_profiles: list[dict[str, Any]],
    mogu_posts: list[dict[str, Any]],
    wish_spots: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """사용자 상호작용 생성 (거리/시간대/관심사 상관관계 반영)"""
    favorites: list[dict[str, Any]] = []
    participations: list[dict[str, Any]] = []
    ratings: list[dict[str, Any]] = []

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

            # 3. 거리 계산 (가장 가까운 위시스팟 기준)
            min_distance = float("inf")
            for spot in user_spots:
                spot_lat, spot_lon = spot["location"]
                post_lat, post_lon = post["mogu_spot"]
                distance = calculate_distance(spot_lat, spot_lon, post_lat, post_lon)
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
                datetime.now() - post["created_at"]
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

        # 게시물별 선호도 점수 계산
        post_scores = []
        for post in mogu_posts:
            if post["status"] != "recruiting":
                continue
            score = calculate_preference_score(post)
            post_scores.append((post, score))

        # 점수 순으로 정렬
        post_scores.sort(key=lambda x: x[1], reverse=True)

        # 상위 게시물들에 대해 상호작용 생성
        num_interactions = min(base_interactions, len(post_scores))

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
            post, score = post_scores[i]

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
            current_year = datetime.now().year
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

            # 모구 인원 체킹: 자리가 있을 때만 참여 가능
            # 현재 해당 게시물의 참여자 수 확인
            current_participants = len(
                [
                    p
                    for p in participations
                    if p["mogu_post_id"] == post["id"]
                    and p["status"] in ["applied", "accepted", "fulfilled"]
                ]
            )

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

                participation = {
                    "user_id": user["id"],
                    "mogu_post_id": post["id"],
                    "status": status,
                    "applied_at": applied_time,
                    "decided_at": (
                        generate_realistic_datetime(90) if status != "applied" else None
                    ),
                }
                participations.append(participation)

                # fulfilled인 경우 평가 생성
                if status == "fulfilled" and random.random() < RATING_PROBABILITY:
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

                    rating = {
                        "id": str(uuid.uuid4()),
                        "mogu_post_id": post["id"],
                        "reviewer_id": user["id"],
                        "reviewee_id": post["user_id"],
                        "stars": rating_score,
                        "keywords": keywords,
                        "created_at": generate_realistic_datetime(90),
                    }
                    ratings.append(rating)

    # 참여 생성 후 joined_count 업데이트
    print("🔄 joined_count 업데이트 중...")
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

        # 상태도 업데이트 (비즈니스 로직 반영)
        fulfilled_participants = len(
            [
                p
                for p in participations
                if p["mogu_post_id"] == post["id"] and p["status"] == "fulfilled"
            ]
        )

        if fulfilled_participants > 0:
            # fulfilled 참여자가 있으면 반드시 completed 상태
            post["status"] = "completed"
        elif (
            post["status"] == "recruiting"
            and actual_participants >= post["target_count"]
        ):
            # 목표 인원에 도달했으면 locked로 변경
            post["status"] = "locked"

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

    # 각 게시물별로 댓글 생성
    for post in mogu_posts:
        if post["status"] != "recruiting":
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

        for i in range(num_comments):
            commenter = random.choice(participants)
            content = random.choice(comment_templates)

            comment = {
                "id": str(uuid.uuid4()),
                "mogu_post_id": post["id"],
                "user_id": commenter,
                "content": content,
                "created_at": generate_realistic_datetime(90),
            }
            comments.append(comment)

    return comments


async def main(seed: int = 42) -> None:
    """메인 실행 함수"""
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

    # 6. 데이터 저장
    print("💾 데이터 저장 중...")
    dummy_data: dict[str, Any] = {
        "users": user_profiles,
        "wish_spots": wish_spots,
        "mogu_posts": mogu_posts,
        "favorites": favorites,
        "participations": participations,
        "ratings": ratings,
        "comments": comments,
        "generated_at": datetime.now().isoformat(),
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

    # JSON 파일로 저장
    with open("dummy_data.json", "w", encoding="utf-8") as f:
        json.dump(dummy_data, f, ensure_ascii=False, indent=2, default=str)

    print("🎉 더미 데이터 생성 완료!")
    print("📁 파일 저장: dummy_data.json")
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
