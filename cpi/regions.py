"""
Бүсийн индекс (Бүлэг.xlsx → «бүс», «Шинэ бүс»).

Бүс = аймгуудын жигнэсэн дундаж (улсын national-тай ижил арга):

    I_region,row(t) = Σ_{a∈R} (H_a,row · I_a,row(t)) / Σ_{a∈R} H_a,row
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .engine import CPIResult, inflation_yoy, inflation_mom
from .export import MAJOR_ROWS

_DATA = Path(__file__).resolve().parent.parent / "data"


def load_regions() -> dict[str, Any]:
    with open(_DATA / "regions.json", encoding="utf-8") as f:
        return json.load(f)


def aggregate_region_codes(
    result: CPIResult,
    codes: list[str],
    rows: list[int] | None = None,
) -> dict[str, Any]:
    """
    Өгөгдсөн аймгийн кодуудын жигнэсэн индекс (мөр бүрт).
    """
    if rows is None:
        rows = MAJOR_ROWS
    codes = [c for c in codes if c in result.regions]
    n = len(result.months)
    by_row = {n_.row: n_ for n_ in result.structure}

    out_rows: dict[int, dict[str, Any]] = {}
    for row in rows:
        w_sum = 0.0
        series = [0.0] * n
        for code in codes:
            rr = result.regions[code]
            w = rr.weights.get(row, 0.0) or 0.0
            w_sum += w
            idx = rr.indices.get(row)
            if idx is None:
                continue
            for t in range(n):
                series[t] += w * idx[t]
        if w_sum == 0:
            series = [100.0] * n
        else:
            series = [s / w_sum for s in series]
        node = by_row.get(row)
        out_rows[row] = {
            "row": row,
            "name": node.name if node else str(row),
            "weight": w_sum,
            "indices": series,
            "yoy": inflation_yoy(series),
            "mom": inflation_mom(series),
        }

    overall = out_rows.get(8, {}).get("indices", [100.0] * n)
    return {
        "codes": codes,
        "weight_total": out_rows.get(8, {}).get("weight", 0.0),
        "overall": overall,
        "rows": out_rows,
    }


def compute_all_regions(result: CPIResult) -> dict[str, dict[str, Any]]:
    """
    traditional + new бүсийн схемийг тооцоолно.

    Returns
    -------
    {
      "traditional": { region_name: {...} },
      "new": { region_name: {...} },
    }
    """
    cfg = load_regions()
    out: dict[str, dict[str, Any]] = {}
    for scheme in ("traditional", "new"):
        scheme_out = {}
        for region_name, members in cfg[scheme].items():
            codes = [m["code"] for m in members]
            agg = aggregate_region_codes(result, codes)
            agg["name"] = region_name
            agg["members"] = members
            scheme_out[region_name] = agg
        out[scheme] = scheme_out
    return out
