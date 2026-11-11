"""scoring 模块的单测。运行方式：
    python -m pytest tests/ -q
或直接：
    python tests/test_scoring.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.algo.scoring import (  # noqa: E402
    MODE_WEIGHTS,
    Poi,
    ScoreContext,
    buffer_radius_m,
    factor_heat,
    factor_interest,
    haversine_m,
    order_along_line,
    plan_waypoints,
    score_poi,
    select_waypoints,
    waypoint_target_count,
    rank,
)

WUDA = (114.3608, 30.5387)      # 武汉大学珞珈门
TANHUALIN = (114.3165, 30.5497)  # 昙华林


def _ctx(tag_order=("art", "history"), weights=None):
    d = haversine_m(WUDA, TANHUALIN)
    return ScoreContext(
        origin=WUDA,
        destination=TANHUALIN,
        tag_order=tag_order,
        radius_m=buffer_radius_m(d),
        avg_stay_minutes=12.0,
        weights=dict(weights or MODE_WEIGHTS["balanced"]),
    )


def _poi(pid, lng, lat, typecode="050500", tags=("art",), rating=None, stay=15):
    return Poi(
        poi_id=pid, name=pid, lng=lng, lat=lat,
        typecode=typecode, tag_ids=tuple(tags), rating=rating, stay_minutes=stay,
    )


def test_haversine_city_scale():
    d = haversine_m(WUDA, TANHUALIN)
    assert 4000 < d < 5200, d


def test_haversine_zero():
    assert haversine_m(WUDA, WUDA) < 0.001


def test_buffer_radius_clamped():
    assert buffer_radius_m(1000) == 500.0
    assert buffer_radius_m(2000) == 1000.0
    assert buffer_radius_m(20000) == 2500.0


def test_waypoint_target_count_bands():
    assert waypoint_target_count(2000) == 3
    assert waypoint_target_count(3000) == 4
    assert waypoint_target_count(4000) == 4
    assert waypoint_target_count(6000) == 5
    assert waypoint_target_count(9000) == 6


def test_interest_match_weighted():
    poi = _poi("a", 114.35, 30.54, tags=("art",))
    # 首位标签权重 1.0，总权重 1.0 + 0.7 = 1.7
    assert abs(factor_interest(poi, ("art", "history")) - 1.0 / 1.7) < 1e-6


def test_interest_match_no_hit():
    poi = _poi("a", 114.35, 30.54, tags=("food",))
    assert factor_interest(poi, ("art", "history")) == 0.0


def test_interest_match_empty_order():
    poi = _poi("a", 114.35, 30.54)
    assert factor_interest(poi, ()) == 0.0


def test_heat_default_and_full():
    assert factor_heat(Poi("x", "x", 0, 0, rating=None)) == 0.5
    assert factor_heat(Poi("x", "x", 0, 0, rating=5)) == 1.0


def test_score_within_unit_interval():
    ctx = _ctx()
    for poi in [
        _poi("a", 114.35, 30.54),
        _poi("b", 114.34, 30.545, typecode="110100", tags=("park",), rating=4.2, stay=10),
        _poi("c", 114.32, 30.548, typecode="140300", tags=(), rating=None, stay=20),
    ]:
        score, detail = score_poi(poi, ctx)
        assert 0.0 <= score <= 1.0, score
        assert set(detail) == {"M", "A", "H", "T", "V"}
        for v in detail.values():
            assert 0.0 <= v <= 1.0


def test_weights_sum_to_one():
    for mode, w in MODE_WEIGHTS.items():
        assert abs(sum(w.values()) - 1.0) < 1e-9, mode


def test_select_waypoints_respects_gap():
    # 两点相距约 55 米，只能选一个
    a = _poi("a", 114.3000, 30.5000, typecode="050500")
    b = _poi("b", 114.3000, 30.5005, typecode="110100")
    ranked = rank([a, b], _ctx())
    chosen = select_waypoints(ranked, target_n=3, min_gap_m=200)
    assert len(chosen) == 1, [p.poi_id for p in chosen]


def test_select_waypoints_type_cap():
    # 同分类码 3 个，彼此距离足够，最多选 2 个
    pois = [
        _poi("a", 114.3000, 30.5000, typecode="050500"),
        _poi("b", 114.3200, 30.5000, typecode="050500"),
        _poi("c", 114.3400, 30.5000, typecode="050500"),
    ]
    ranked = rank(pois, _ctx())
    chosen = select_waypoints(ranked, target_n=3, min_gap_m=200, max_same_type=2)
    assert len(chosen) == 2, [p.poi_id for p in chosen]


def test_order_along_line_monotonic():
    pois = [
        _poi("far", 114.3180, 30.5490),
        _poi("near", 114.3550, 30.5400),
        _poi("mid", 114.3350, 30.5450),
    ]
    ordered = order_along_line(pois, WUDA, TANHUALIN)
    assert [p.poi_id for p in ordered] == ["near", "mid", "far"]


def test_plan_waypoints_end_to_end():
    pois = [
        _poi("p1", 114.3520, 30.5402, typecode="140400", tags=("art",), rating=4.6),
        _poi("p2", 114.3455, 30.5455, typecode="140300", tags=("art", "history"), rating=4.7),
        _poi("p3", 114.3380, 30.5488, typecode="110200", tags=("history",)),
        _poi("p4", 114.3165, 30.5497, typecode="110100", tags=("park",), rating=4.4, stay=15),
    ]
    ctx = _ctx()
    chosen, ranked = plan_waypoints(pois, ctx)
    assert len(ranked) == 4
    assert 3 <= len(chosen) <= 6
    # 沿线投影应单调递增
    from app.algo.scoring import _project_t
    ts = [_project_t(p.xy, ctx.origin, ctx.destination) for p in chosen]
    assert ts == sorted(ts), ts


def test_rank_is_deterministic():
    pois = [
        _poi("a", 114.3000, 30.5000, typecode="050500", rating=None),
        _poi("b", 114.3000, 30.5000, typecode="050500", rating=None),
    ]
    r1 = [p.poi_id for p, _s, _d in rank(pois, _ctx())]
    r2 = [p.poi_id for p, _s, _d in rank(list(reversed(pois)), _ctx())]
    assert r1 == r2 == sorted(r1)


def test_mode_weights_change_ranking():
    near_unmatched = _poi("near", 114.3580, 30.5390, typecode="050500", tags=("food",))
    far_matched = _poi("far", 114.3300, 30.5600, typecode="050500", tags=("art",))
    nearby = [near_unmatched, far_matched]

    top_max = rank(nearby, _ctx(weights=MODE_WEIGHTS["max"]))[0][0].poi_id
    top_short = rank(nearby, _ctx(weights=MODE_WEIGHTS["shortest"]))[0][0].poi_id
    assert top_max == "far"      # 兴趣最大化：匹配标签的胜出
    assert top_short == "near"   # 最短路线：离得近的胜出


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL {name}: {e}")
    print("\n失败数:", failed)
    sys.exit(1 if failed else 0)
