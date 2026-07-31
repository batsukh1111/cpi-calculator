"""
Барааны тусгай бүлгийн индекс (Бүлэг.xlsx → «барааны бүлэг»).

Тусгай ангилал (дотоод, импорт, мах, бараа, үйлчилгээ, суурь инфляц …)-ийн
флагтай elementary бараануудыг жингээр жигнэж дахин нэгтгэнэ:

    I_g(t) = Σ_{i∈G} (w_i · I_i(t)) / Σ_{i∈G} w_i

- Улаанбаатар: sheet 20-ийн жин + индекс
- Улс: national жин (аймгуудын нийлбэр) + national elementary индекс
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .engine import CPIResult, RegionResult, NationalResult, inflation_yoy, inflation_mom

_DATA = Path(__file__).resolve().parent.parent / "data"


def load_special_groups() -> dict[str, Any]:
    with open(_DATA / "special_groups.json", encoding="utf-8") as f:
        return json.load(f)


def special_group_index(
    member_rows: list[int],
    weights: dict[int, float],
    indices: dict[int, list[float]],
    n_months: int,
) -> tuple[list[float], float]:
    """
    Returns (monthly_index_series, total_weight).
    Зөвхөн жин > 0 болон индекс байгаа мөрүүдийг оролцуулна.
    """
    members = []
    total_w = 0.0
    for r in member_rows:
        w = weights.get(r, 0.0) or 0.0
        if w == 0 or r not in indices:
            continue
        members.append((r, w))
        total_w += w

    if total_w == 0:
        return [100.0] * n_months, 0.0

    out = []
    for t in range(n_months):
        s = 0.0
        for r, w in members:
            s += w * indices[r][t]
        out.append(s / total_w)
    return out, total_w


def compute_special_groups_for_scope(
    result: CPIResult,
    weights: dict[int, float],
    indices: dict[int, list[float]],
    groups_cfg: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Нэг scope (UB эсвэл улс)-д бүх тусгай бүлгийн индекс.

    Returns
    -------
    { group_key: { label_mn, weight, indices, yoy, mom } }
    """
    if groups_cfg is None:
        groups_cfg = load_special_groups()
    labels = groups_cfg["labels_mn"]
    groups = groups_cfg["groups"]
    n = len(result.months)
    out: dict[str, dict[str, Any]] = {}

    for key, rows in groups.items():
        series, w = special_group_index(rows, weights, indices, n)
        out[key] = {
            "key": key,
            "label_mn": labels.get(key, key),
            "weight": w,
            "n_items": sum(
                1
                for r in rows
                if (weights.get(r, 0.0) or 0.0) > 0 and r in indices
            ),
            "indices": series,
            "yoy": inflation_yoy(series),
            "mom": inflation_mom(series),
        }
    return out


def compute_ub_and_national_special(
    result: CPIResult,
    groups_cfg: dict[str, Any] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Улаанбаатар (20) + Улс — тусгай бүлгийн индекс.

    Returns { 'ulaanbaatar': {...}, 'national': {...} }
    """
    if groups_cfg is None:
        groups_cfg = load_special_groups()

    ub = result.regions.get("20")
    if ub is None:
        raise KeyError(
            "Улаанбаатар (sheet 20) үр дүнд алга. calculate() үед 20-г оруулна уу."
        )

    return {
        "ulaanbaatar": compute_special_groups_for_scope(
            result, ub.weights, ub.indices, groups_cfg
        ),
        "national": compute_special_groups_for_scope(
            result, result.national.weights, result.national.indices, groups_cfg
        ),
    }
