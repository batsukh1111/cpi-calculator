"""
Инфляцын оролцоо (contribution).

ҮСХ Excel-ийн томьёотой ижил:

    Cont_i (нэгж, pp) = w_i * (I_i,t − I_i,base) / I_overall,base

    Share_i (%)        = Cont_i / Cont_overall * 100

  w_i            — харьцангуй жин (ерөнхий = 100)
  I_i,t          — бүлгийн одоогийн индекс
  I_i,base       — харьцуулах сарын индекс
  I_overall,base — ерөнхий индексийн харьцуулах сарын утга

Cont_overall = 100 * (I_t − I_base) / I_base  (= инфляцын хувь)
"""

from __future__ import annotations

from typing import Any

from .engine import CPIResult, RegionResult
from .export import MAJOR_ROWS
from .special_groups import load_special_groups, special_group_index


def rel_weight(weights: dict[int, float], row: int) -> float:
    total = weights.get(8, 0.0) or 0.0
    if total == 0:
        return 0.0
    return (weights.get(row, 0.0) or 0.0) / total * 100.0


def contribution_pp(
    rel_w: float,
    idx_t: float,
    idx_base: float,
    overall_base: float,
) -> float | None:
    """Нэг бүлгийн оролцоо (percentage points)."""
    if overall_base is None or overall_base == 0:
        return None
    if idx_t is None or idx_base is None:
        return None
    return rel_w * (idx_t - idx_base) / overall_base


def contribution_share(cont: float | None, cont_overall: float | None) -> float | None:
    if cont is None or cont_overall is None or cont_overall == 0:
        return None
    return cont / cont_overall * 100.0


def group_contributions(
    weights: dict[int, float],
    indices: dict[int, list[float]],
    t: int,
    t_base: int,
    rows: list[int] | None = None,
    names: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """
    COICOP мөрүүдийн оролцоо.

    Returns list with overall first (row 8), then groups.
    """
    if rows is None:
        rows = MAJOR_ROWS
    if t_base is None or t_base < 0:
        return []

    overall_series = indices.get(8, [])
    if t >= len(overall_series) or t_base >= len(overall_series):
        return []

    overall_base = overall_series[t_base]
    overall_t = overall_series[t]
    cont_overall = contribution_pp(100.0, overall_t, overall_base, overall_base)

    out = []
    for row in rows:
        series = indices.get(row)
        if not series or t >= len(series) or t_base >= len(series):
            continue
        rw = rel_weight(weights, row) if row != 8 else 100.0
        # for row 8, weight is 100
        if row == 8:
            rw = 100.0
        idx_t = series[t]
        idx_b = series[t_base]
        cont = contribution_pp(rw, idx_t, idx_b, overall_base)
        infl = None
        if idx_b and idx_b != 0:
            infl = (idx_t / idx_b - 1.0) * 100.0
        name = (names or {}).get(row, str(row))
        out.append(
            {
                "row": row,
                "name": name,
                "weight": rw,
                "index": idx_t,
                "index_base": idx_b,
                "inflation": infl,
                "contrib_pp": cont,
                "contrib_share": contribution_share(cont, cont_overall),
                "is_overall": row == 8,
            }
        )
    return out


def special_contributions(
    result: CPIResult,
    scope: str,
    t: int,
    t_base: int,
) -> list[dict[str, Any]]:
    """
    Тусгай бүлгүүдийн оролцоо (улс эсвэл УБ).

    scope: 'national' | '20'
    """
    if t_base is None or t_base < 0:
        return []

    groups_cfg = load_special_groups()
    labels = groups_cfg["labels_mn"]
    groups = groups_cfg["groups"]
    n = len(result.months)

    if scope == "national":
        weights = result.national.weights
        indices = result.national.indices
        overall = result.national.overall
    else:
        if scope not in result.regions:
            return []
        rr = result.regions[scope]
        weights = rr.weights
        indices = rr.indices
        overall = rr.overall

    if t >= len(overall) or t_base >= len(overall):
        return []

    overall_base = overall[t_base]
    overall_t = overall[t]
    cont_overall = contribution_pp(100.0, overall_t, overall_base, overall_base)
    total_w = weights.get(8, 0.0) or 0.0

    out = [
        {
            "key": "overall",
            "name": "ЕРӨНХИЙ ИНДЕКС",
            "weight": 100.0,
            "index": overall_t,
            "index_base": overall_base,
            "inflation": (overall_t / overall_base - 1.0) * 100.0 if overall_base else None,
            "contrib_pp": cont_overall,
            "contrib_share": 100.0 if cont_overall else None,
            "is_overall": True,
        }
    ]

    for key, members in groups.items():
        series, abs_w = special_group_index(members, weights, indices, n)
        if t >= len(series) or t_base >= len(series):
            continue
        rw = (abs_w / total_w * 100.0) if total_w else 0.0
        idx_t = series[t]
        idx_b = series[t_base]
        cont = contribution_pp(rw, idx_t, idx_b, overall_base)
        infl = (idx_t / idx_b - 1.0) * 100.0 if idx_b else None
        out.append(
            {
                "key": key,
                "name": labels.get(key, key),
                "weight": rw,
                "index": idx_t,
                "index_base": idx_b,
                "inflation": infl,
                "contrib_pp": cont,
                "contrib_share": contribution_share(cont, cont_overall),
                "is_overall": False,
            }
        )
    return out


def compute_contributions(
    result: CPIResult,
    t: int,
    t_base: int,
    base_label: str = "",
) -> dict[str, Any]:
    """
    Улс + УБ: COICOP бүлэг + тусгай бүлгийн оролцоо.
    """
    names = {n.row: (n.name or str(n.row)) for n in result.structure}

    national_groups = group_contributions(
        result.national.weights,
        result.national.indices,
        t,
        t_base,
        rows=MAJOR_ROWS,
        names=names,
    )
    national_special = special_contributions(result, "national", t, t_base)

    ub_groups = []
    ub_special = []
    if "20" in result.regions:
        ub = result.regions["20"]
        ub_groups = group_contributions(
            ub.weights, ub.indices, t, t_base, rows=MAJOR_ROWS, names=names
        )
        ub_special = special_contributions(result, "20", t, t_base)

    return {
        "base_period": base_label,
        "t": t,
        "t_base": t_base,
        "national": {
            "groups": national_groups,
            "special": national_special,
        },
        "ulaanbaatar": {
            "groups": ub_groups,
            "special": ub_special,
        },
    }
