"""AI 추천 시스템 유틸리티

V0 (Content-Based) + V1 (Collaborative Filtering) 하이브리드 추천 시스템
"""

import logging
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.requests import MoguPostListQueryParams

logger = logging.getLogger(__name__)

# ===== 하이퍼파라미터 =====
CANDIDATE_LIMIT = 300
W0_COLD = 0.85  # 콜드 유저: V0 중심
W1_COLD = 0.15
W0_WARM = 0.65  # 히스토리 보유: 균형
W1_WARM = 0.35

HISTORY_LIMIT = 50  # 사용자 히스토리 상위 n개
EPSILON = 1e-9  # 0으로 나누기 방지


# ===== 카테고리/마켓 매핑 =====
CAT_IDX = {"생활용품": 0, "식품/간식류": 1, "패션/잡화": 2, "뷰티/헬스케어": 3}
MARKETS = [
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
MARKET_IDX = {m: i for i, m in enumerate(MARKETS)}

# ===== V0 벡터 차원 =====
V0_DIM = 4 + 10 + 24  # 카테고리(4) + 마켓(10) + 시간대(24) = 38차원


# ===== 벡터 유틸리티 함수 =====
def _minmax01(arr: np.ndarray) -> np.ndarray:
    """MinMax 정규화 (0-1)"""
    if arr.size == 0:
        return arr
    lo, hi = float(np.min(arr)), float(np.max(arr))
    if hi - lo < EPSILON:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def _cosine_batch(u: np.ndarray, P: np.ndarray) -> Any:  # noqa: ANN401
    """배치 코사인 유사도 계산

    Args:
        u: 사용자 벡터 (D,)
        P: 게시물 벡터 행렬 (N, D)

    Returns:
        코사인 유사도 배열 (N,)
    """
    u_norm = np.linalg.norm(u) + EPSILON
    P_norm = np.linalg.norm(P, axis=1) + EPSILON
    return (P @ u) / (P_norm * u_norm)


# ===== V0: 사용자 벡터 생성 =====
def build_user_vector(user_row: Any) -> Any:  # noqa: ANN401
    """사용자 프로필을 벡터로 변환

    벡터 구성 (38차원):
    - 카테고리 (4차원)
    - 마켓 (10차원)
    - 시간대 (24차원)

    Args:
        user_row: 사용자 프로필 (interested_categories, wish_markets, wish_times)

    Returns:
        사용자 벡터 (38차원)
    """
    # 1. 카테고리 선호 (Multi-Hot: 4차원)
    cat = np.zeros(len(CAT_IDX))
    for c in user_row.interested_categories or []:
        if c in CAT_IDX:
            cat[CAT_IDX[c]] = 1.0

    # 2. 마켓 선호 (Multi-Hot: 10차원)
    market = np.zeros(len(MARKETS))
    for m in user_row.wish_markets or []:
        if m in MARKET_IDX:
            market[MARKET_IDX[m]] = 1.0

    # 3. 시간대 선호 (24차원)
    hours = np.array(user_row.wish_times or [0] * 24, dtype=float)
    hours = hours.clip(0, 1)

    # 최종 벡터: [cat(4), market(10), hours(24)] = 38차원
    u = np.concatenate([cat, market, hours]).astype(float)
    assert u.shape[0] == V0_DIM, (
        f"User vector dimension mismatch: {u.shape[0]} != {V0_DIM}"
    )
    return u


# ===== V0: 게시물 벡터 생성 =====
def build_post_vector(candidate: Any) -> Any:  # noqa: ANN401
    """게시물을 벡터로 변환

    벡터 구성 (38차원):
    - 카테고리 (4차원)
    - 마켓 (10차원)
    - 시간대 (24차원)

    Args:
        candidate: 게시물 후보 (category, mogu_market, hour)

    Returns:
        게시물 벡터 (38차원)
    """
    # 1. 카테고리 (One-Hot: 4차원)
    cat = np.zeros(len(CAT_IDX))
    if candidate.category in CAT_IDX:
        cat[CAT_IDX[candidate.category]] = 1.0

    # 2. 마켓 (One-Hot: 10차원)
    market = np.zeros(len(MARKETS))
    if candidate.mogu_market in MARKET_IDX:
        market[MARKET_IDX[candidate.mogu_market]] = 1.0

    # 3. 시간대 (24차원 One-Hot)
    hour_oh = np.zeros(24)
    if candidate.hour is not None:
        hour_oh[int(candidate.hour) % 24] = 1.0

    # 최종 벡터: [cat(4), market(10), hour(24)] = 38차원
    p = np.concatenate([cat, market, hour_oh]).astype(float)
    assert p.shape[0] == V0_DIM, (
        f"Post vector dimension mismatch: {p.shape[0]} != {V0_DIM}"
    )
    return p


# ===== V1: 사용자 히스토리 조회 =====
async def fetch_user_history_post_ids(session: AsyncSession, user_id: str) -> list[str]:
    """사용자 히스토리 게시물 ID 조회 (찜 + 참여)

    강한 신호(참여) 우선, 최근 HISTORY_LIMIT개

    Args:
        session: DB 세션
        user_id: 사용자 ID

    Returns:
        게시물 ID 리스트
    """
    q = text(
        """
    with u_hist as (
      -- 강한 신호: 참여 (가중치 2.0)
      (select mogu_post_id as pid, decided_at as t, 2.0 as w
       from participation
       where user_id = :uid and status in ('accepted','fulfilled')
       order by coalesce(decided_at, applied_at) desc
       limit :lim)
      union all
      -- 약한 신호: 찜하기 (가중치 1.0)
      (select mogu_post_id as pid, created_at as t, 1.0 as w
       from mogu_favorite
       where user_id = :uid
       order by created_at desc
       limit :lim)
    )
    select pid from u_hist
    order by t desc
    limit :lim
    """
    )
    rows = (await session.execute(q, {"uid": user_id, "lim": HISTORY_LIMIT})).all()
    return [str(r[0]) for r in rows]


# ===== V1: CF 점수 계산 =====
async def fetch_cf_scores_for_candidates(
    session: AsyncSession,
    candidate_ids: list[str],
    history_ids: list[str],
) -> dict[str, float]:
    """후보군에 대한 CF 점수 계산

    item_item_sim 캐시 테이블에서 후보군(c)과 히스토리(h) 간 유사도 조회
    각 후보군별로 최대 유사도를 점수로 사용

    Args:
        session: DB 세션
        candidate_ids: 후보군 게시물 ID 리스트
        history_ids: 사용자 히스토리 게시물 ID 리스트

    Returns:
        {게시물 ID: CF 점수} 딕셔너리
    """
    if not candidate_ids or not history_ids:
        return {cid: 0.0 for cid in candidate_ids}

    try:
        q = text(
            """
        select s.src_post_id as cid, max(s.sim) as score
        from item_item_sim s
        where s.src_post_id = any(:cids) and s.neigh_post_id = any(:hids)
        group by s.src_post_id
        """
        )
        rows = (
            await session.execute(
                q, {"cids": list(candidate_ids), "hids": list(history_ids)}
            )
        ).all()

        d = {str(r.cid): float(r.score or 0.0) for r in rows}

        # 없는 후보는 0
        for cid in candidate_ids:
            if cid not in d:
                d[cid] = 0.0

        # V1 점수 통계 로깅
        scores = [v for v in d.values() if v > 0]
        if scores:
            logger.info(
                f"V1 (CF) enabled: {len(scores)}/{len(d)} items with CF scores, "
                f"avg={np.mean(scores):.3f}, max={np.max(scores):.3f}"
            )
        else:
            logger.info("V1 (CF) enabled but no similarity scores found")

        return d
    except Exception as e:
        # item_item_sim 테이블이 없거나 에러 발생 시 모든 점수를 0으로 반환
        # V1 점수가 0이면 V0만으로 추천 진행
        logger.warning(f"V1 (CF) disabled: item_item_sim table not available - {e}")
        return {cid: 0.0 for cid in candidate_ids}


# ===== 후보군 + 피처 로딩 =====
async def fetch_candidates_with_features(
    session: AsyncSession, params: MoguPostListQueryParams
) -> list[Any]:
    """후보군 조회 및 AI 점수 계산용 피처 로딩

    후보군 조건:
    - status='recruiting'
    - mogu_datetime > now()
    - 반경 r 내
    - 카테고리/마켓 필터 (선택)

    피처:
    - dist_km: 사용자와의 거리(km)
    - hour: 모구 시간대(0-23)
    - rep: 모구장 평판(0-1)

    Args:
        session: DB 세션
        params: 쿼리 파라미터

    Returns:
        후보군 리스트 (최대 CANDIDATE_LIMIT개)
    """
    # 완전히 raw SQL (text) 방식으로 구현
    # 동적 WHERE 조건 생성
    where_clauses = [
        "p.status = 'recruiting'",
        "p.mogu_datetime > now()",
        "ST_DWithin(p.mogu_spot::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)",
    ]

    query_params: dict[str, float | int | str] = {
        "lon": params.longitude,
        "lat": params.latitude,
        "radius": params.radius * 1000,
        "limit": CANDIDATE_LIMIT,
    }

    if params.category:
        where_clauses.append("p.category = :cat")
        query_params["cat"] = params.category

    if params.mogu_market:
        where_clauses.append("p.mogu_market = :market")
        query_params["market"] = params.mogu_market

    where_sql = " AND ".join(where_clauses)

    query_sql = text(
        f"""
    SELECT
        p.id::text as id,
        p.user_id::text as host_id,
        p.category,
        p.mogu_market,
        p.mogu_datetime,
        p.price,
        p.labor_fee,
        p.joined_count,
        p.target_count,
        p.created_at,
        ST_Distance(p.mogu_spot::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000.0 as dist_km,
        EXTRACT(hour FROM p.mogu_datetime)::int as hour,
        COALESCE(((COALESCE(mv.avg_stars, 3.0) - 1.0) / 4.0), 0.5)::float as rep
    FROM mogu_post p
    LEFT JOIN mv_host_reputation mv ON mv.reviewee_id = p.user_id
    WHERE {where_sql}
    ORDER BY p.created_at DESC
    LIMIT :limit
    """
    )

    rows = (await session.execute(query_sql, query_params)).mappings().all()
    return list(rows)  # list of Mapping: access with row["id"], row["dist_km"], ...


# ===== 사용자 프로필 조회 =====
async def fetch_user_profile_for_vector(session: AsyncSession, user_id: str) -> Any:
    """벡터 생성용 사용자 프로필 조회

    Args:
        session: DB 세션
        user_id: 사용자 ID

    Returns:
        사용자 프로필 (interested_categories, wish_markets, wish_times)
    """
    q = text(
        """
    select interested_categories, wish_markets, wish_times
    from app_user
    where id = :uid
    """
    )
    row = (await session.execute(q, {"uid": user_id})).first()
    return row


# ===== AI 추천 정렬 메인 함수 =====
async def rank_by_ai(  # noqa: PLR0912, PLR0915
    session: AsyncSession,
    params: MoguPostListQueryParams,
    current_user: User | None,
) -> tuple[list[str], int]:
    """AI 하이브리드 추천 정렬

    V0 (Content-Based) + V1 (Collaborative Filtering) 하이브리드

    Flow:
    1. 후보군 조회 (필수 필터 적용)
    2. V0: 사용자/게시물 벡터 생성 → 코사인 유사도 계산 → 정규화
    3. V1: 사용자 히스토리 × 아이템 유사도 캐시 → CF 점수 계산 → 정규화
    4. 앙상블: final = w0 * v0 + w1 * v1 (콜드/웜 유저별 가중치)
    5. 타이브레이커: 최종점수 → 신선도 → 거리 → 평판
    6. 페이지 슬라이스

    Args:
        session: DB 세션
        params: 쿼리 파라미터
        current_user: 현재 사용자 (None이면 콜드 유저)

    Returns:
        (페이지 게시물 ID 리스트, 전체 개수)
    """
    # 1) 후보군 + 피처 로딩
    logger.info(
        f"AI recommendation started: user_id={current_user.id if current_user else 'anonymous'}, "
        f"category={params.category}, market={params.mogu_market}, radius={params.radius}km"
    )
    cand_rows = await fetch_candidates_with_features(session, params)
    if not cand_rows:
        logger.info("No candidates found")
        return [], 0

    logger.info(f"Candidates loaded: {len(cand_rows)} posts")

    # 2) 사용자 벡터
    user_vec = None
    if current_user:
        up = await fetch_user_profile_for_vector(session, str(current_user.id))
        if up:
            # namedtuple-like object 생성
            class UserProfile:
                def __init__(self, row: Any) -> None:  # noqa: ANN401
                    self.interested_categories = row[0]
                    self.wish_markets = row[1]
                    self.wish_times = row[2]

            user_vec = build_user_vector(UserProfile(up))

    # 3) V0: 콘텐츠 코사인
    P = np.vstack([build_post_vector(r) for r in cand_rows])
    if user_vec is not None:
        v0 = _cosine_batch(user_vec, P)
        v0 = _minmax01(v0)
        # V0 점수 통계 로깅
        v0_nonzero = v0[v0 > 0]
        if len(v0_nonzero) > 0:
            logger.info(
                f"V0 (Content-Based) scores: {len(v0_nonzero)}/{len(v0)} items, "
                f"avg={np.mean(v0_nonzero):.3f}, max={np.max(v0):.3f}"
            )
        else:
            logger.info("V0 (Content-Based) scores: all zeros (no matching features)")
    else:
        v0 = np.zeros(len(cand_rows), dtype=float)
        logger.info("V0 (Content-Based) disabled: user vector not available")

    # 4) V1: 아이템 CF
    v1 = np.zeros_like(v0)
    has_hist = False
    if current_user:
        history_ids = await fetch_user_history_post_ids(session, str(current_user.id))
        if history_ids:
            has_hist = True
            logger.info(
                f"User history: {len(history_ids)} items (favorites + participations)"
            )
            cf_scores = await fetch_cf_scores_for_candidates(
                session, [str(r["id"]) for r in cand_rows], history_ids
            )
            v1 = np.array([cf_scores[str(r["id"])] for r in cand_rows], dtype=float)
            v1 = _minmax01(v1)
            # V1 점수 통계 로깅
            v1_nonzero = v1[v1 > 0]
            if len(v1_nonzero) > 0:
                logger.info(
                    f"V1 (CF) final scores: {len(v1_nonzero)}/{len(v1)} items, "
                    f"avg={np.mean(v1_nonzero):.3f}, max={np.max(v1):.3f}"
                )
        else:
            logger.info("V1 (CF) disabled: user has no history")

    # 5) 앙상블
    if has_hist:
        w0, w1 = W0_WARM, W1_WARM
        logger.info(f"Hybrid ensemble (warm user): w0={w0}, w1={w1}")
    else:
        w0, w1 = W0_COLD, W1_COLD
        logger.info(f"Hybrid ensemble (cold user): w0={w0}, w1={w1}")
    final = w0 * v0 + w1 * v1

    # 최종 점수 통계 로깅
    final_nonzero = final[final > 0]
    if len(final_nonzero) > 0:
        logger.info(
            f"Final hybrid scores: {len(final_nonzero)}/{len(final)} items, "
            f"avg={np.mean(final_nonzero):.3f}, max={np.max(final):.3f}, min={np.min(final_nonzero):.3f}"
        )
    else:
        logger.warning("Final hybrid scores: all zeros (no recommendations)")

    # 6) 타이브레이커: 신선도(desc) → 거리(asc) → 평판(desc)
    created_ts = np.array([r["created_at"].timestamp() for r in cand_rows], dtype=float)
    dist_km = np.array([float(r["dist_km"]) for r in cand_rows], dtype=float)
    rep = np.array([float(r["rep"] or 0.5) for r in cand_rows], dtype=float)

    order_idx = np.lexsort(
        (
            -rep,  # 평판 desc
            dist_km,  # 거리 asc
            -created_ts,  # 신선도 desc
            -final,  # 최종 점수 desc (lexsort는 역순으로 읽으니 마지막이 1차 기준)
        )
    )

    sorted_rows = [cand_rows[i] for i in order_idx]
    sorted_ids = [str(r["id"]) for r in sorted_rows]
    total = len(sorted_ids)

    # 페이지 슬라이스
    start = (params.page - 1) * params.size
    end = start + params.size
    page_ids = sorted_ids[start:end]

    # 최종 결과 로깅
    logger.info(
        f"AI recommendation completed: total={total}, page={params.page}, "
        f"returned={len(page_ids)} items"
    )

    # 반환된 페이지의 모든 게시물 점수 로깅
    if len(page_ids) > 0:
        score_log = f"\n{'=' * 80}\n"
        score_log += f"📊 Page {params.page} - AI Recommendation Scores\n"
        score_log += f"{'=' * 80}\n"
        for i in range(len(page_ids)):
            idx = order_idx[start + i]  # 전체 정렬에서의 인덱스
            post_id = sorted_ids[start + i]
            category = cand_rows[idx]["category"]
            market = cand_rows[idx]["mogu_market"]
            score_log += (
                f"[{i + 1:2d}] {post_id} | "
                f"final={final[idx]:.4f} (v0={v0[idx]:.4f} + v1={v1[idx]:.4f}) | "
                f"{category} @ {market} | "
                f"{dist_km[idx]:.2f}km\n"
            )
        score_log += f"{'=' * 80}\n"
        logger.info(score_log)

    return page_ids, total
