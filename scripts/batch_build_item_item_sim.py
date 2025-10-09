#!/usr/bin/env python3
"""
item_item_sim 배치 빌더

PostgreSQL (SQLAlchemy Core) + 순수 파이썬으로 아이템-아이템 코사인 Top-K 계산/적재

실행 예시:
    poetry run python scripts/batch_build_item_item_sim.py
"""

import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL as SQLA_URL

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings  # noqa: E402

settings = get_settings()

# ===== 하이퍼파라미터 =====
K_NEIGHBORS = int(os.getenv("SIM_TOPK", "100"))  # 아이템당 이웃 개수
MIN_COMMON = int(os.getenv("SIM_MIN_COMMON", "2"))  # 최소 공통 사용자 수
MIN_SIM = float(os.getenv("SIM_MIN_SIM", "0.05"))  # 최소 유사도
LAMBDA = float(os.getenv("SIM_LAMBDA", "5.0"))  # 베이지안 스무딩 계수
LIMIT_USERS = int(os.getenv("SIM_LIMIT_USERS", "0"))  # 0이면 전체, 디버깅용 부분 샘플


def load_interactions(engine: Engine) -> list[tuple[str, str, float]]:
    """
    (user_id, post_id, weight) 리스트를 로드 (가중치 합산 후 반환)

    가중치:
    - 참여(accepted/fulfilled): 2.0
    - 찜하기: 1.0
    - 신청(applied): 0.5
    """
    sql = """
    with raw as (
      -- 강한 신호: 참여
      select user_id, mogu_post_id as post_id, 2.0 as w
      from participation
      where status in ('accepted','fulfilled')
      union all
      -- 약한 신호: 찜하기
      select user_id, mogu_post_id, 1.0
      from mogu_favorite
      union all
      -- 중간 신호: 신청만
      select user_id, mogu_post_id, 0.5
      from participation
      where status = 'applied'
    ),
    agg as (
      select user_id, post_id, sum(w) as w
      from raw
      group by user_id, post_id
    )
    select user_id::text, post_id::text, w::float8
    from agg
    """
    if LIMIT_USERS > 0:
        sql += " order by user_id limit :lim"

    with engine.connect() as conn:
        if LIMIT_USERS > 0:
            rows = conn.execute(text(sql), {"lim": LIMIT_USERS}).fetchall()
        else:
            rows = conn.execute(text(sql)).fetchall()

    return [(r[0], r[1], float(r[2])) for r in rows]


def build_item_cosine(
    interactions: list[tuple[str, str, float]],
) -> dict[str, list[tuple[str, float, int]]]:
    """
    Item-Item cosine 유사도 + 베이지안 보정 적용
    (공통 사용자 수가 적은 쌍의 유사도를 자동 패널티)

    Returns:
        topk: dict[src] -> list[(neigh, sim_bayes, cnt)]
    """
    # user -> [(item, weight), ...]
    by_user: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for uid, pid, w in interactions:
        by_user[uid].append((pid, w))

    dot: dict[tuple[str, str], float] = defaultdict(float)  # (i,j) -> sum w_i*w_j
    cnt: dict[tuple[str, str], int] = defaultdict(int)  # (i,j) -> common user count
    norm: dict[str, float] = defaultdict(float)  # i -> sum w_i^2

    # 누적
    for _, items in by_user.items():
        # 정규화 누적
        for pid, w in items:
            norm[pid] += w * w
        # 쌍 내적 누적
        L = len(items)
        for a in range(L):
            i, wi = items[a]
            for b in range(a + 1, L):
                j, wj = items[b]
                key = (i, j) if i < j else (j, i)
                dot[key] += wi * wj
                cnt[key] += 1

    # cosine 계산 + 베이지안 보정 + Top-K
    neighs: dict[str, list[tuple[str, float, int]]] = defaultdict(list)
    for (i, j), d in dot.items():
        common_users = cnt[(i, j)]
        if common_users < MIN_COMMON:
            continue
        ni = math.sqrt(norm[i]) if norm[i] > 0 else 0.0
        nj = math.sqrt(norm[j]) if norm[j] > 0 else 0.0
        if ni == 0.0 or nj == 0.0:
            continue

        # 기본 코사인 유사도
        sim = d / (ni * nj)

        # 베이지안 보정 (신뢰도 반영)
        # 공통 사용자 수가 적을수록 유사도에 패널티
        sim_bayes = (common_users / (common_users + LAMBDA)) * sim

        if sim_bayes < MIN_SIM:
            continue
        neighs[i].append((j, sim_bayes, common_users))
        neighs[j].append((i, sim_bayes, common_users))

    # 각 아이템별 Top-K 자르기
    for i in list(neighs.keys()):
        neighs[i].sort(key=lambda x: x[1], reverse=True)
        neighs[i] = neighs[i][:K_NEIGHBORS]

    return neighs


def write_item_item_sim(
    engine: Engine, neighs: dict[str, list[tuple[str, float, int]]]
) -> None:
    """
    item_item_sim 테이블을 재작성(트렁케이트 후 벌크 인서트)
    """
    rows: list[tuple[str, str, float, int]] = []
    for src, lst in neighs.items():
        for neigh, sim, cnt in lst:
            if src == neigh:
                continue
            rows.append((src, neigh, sim, cnt))

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE item_item_sim"))
        # 벌크 insert (5000개씩 청크)
        chunksz = 5000
        for i in range(0, len(rows), chunksz):
            chunk = rows[i : i + chunksz]
            values_sql = ", ".join(
                [f"(:s{k}, :n{k}, :v{k}, :c{k}, now())" for k in range(len(chunk))]
            )
            params: dict[str, str | float | int] = {}
            for k, (s, n, v, c) in enumerate(chunk):
                params[f"s{k}"] = s
                params[f"n{k}"] = n
                params[f"v{k}"] = float(v)
                params[f"c{k}"] = int(c)
            conn.execute(
                text(
                    f"INSERT INTO item_item_sim (src_post_id, neigh_post_id, sim, common_user_count, updated_at) VALUES {values_sql}"
                ),
                params,
            )


def main() -> None:
    """메인 실행 함수"""
    start = time.time()

    # DB 연결
    # URL 객체를 직접 사용하여 인코딩 문제 방지
    db_url = SQLA_URL.create(
        drivername="postgresql+psycopg2",
        username=settings.database.username,
        password=settings.database.password.get_secret_value(),
        host=settings.database.hostname,
        port=settings.database.port,
        database=settings.database.db,
    )
    engine = create_engine(db_url, future=True)

    print(
        f"DB 연결: {settings.database.hostname}:{settings.database.port}/{settings.database.db}"
    )

    print("⬇️  상호작용 데이터 로딩 중...")
    inter = load_interactions(engine)
    print(f"   -> {len(inter):,} 개의 상호작용")

    if not inter:
        print("❌ 상호작용 데이터가 없습니다. 찜하기/참여 데이터를 먼저 생성하세요.")
        return

    print("🔧 아이템-아이템 코사인 유사도 계산 중 (베이지안 보정 적용)...")
    neighs = build_item_cosine(inter)
    total_pairs = sum(len(v) for v in neighs.values())
    print(f"   -> {len(neighs):,} 개 아이템, {total_pairs:,} 개 유사도 쌍 (λ={LAMBDA})")

    if not neighs:
        print(
            "❌ 유사도 쌍이 생성되지 않았습니다. MIN_COMMON 또는 MIN_SIM 값을 조정하세요."
        )
        return

    print("💾 item_item_sim 테이블에 저장 중...")
    write_item_item_sim(engine, neighs)

    elapsed = time.time() - start
    print(f"✅ 완료! (소요 시간: {elapsed:.2f}초)")
    print("\n📊 통계:")
    print(f"   - 아이템 수: {len(neighs):,}")
    print(f"   - 유사도 쌍 수: {total_pairs:,}")
    print(f"   - Top-K: {K_NEIGHBORS}")
    print(f"   - 최소 공통 사용자: {MIN_COMMON}")
    print(f"   - 최소 유사도: {MIN_SIM}")
    print(f"   - 베이지안 λ: {LAMBDA} (공통 사용자 수 기반 신뢰도 보정)")


if __name__ == "__main__":
    main()
