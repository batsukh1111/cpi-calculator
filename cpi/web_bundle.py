"""
GitHub Pages / онлайн статик сайт-д зориулсан JSON багц.

Бүх сарын индекс, жин, тусгай бүлэг, бүс — браузер дээр
харьцуулалт, contribution-ийг шууд JS-ээр бодно.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .engine import CPIResult
from .export import MAJOR_ROWS
from .special_groups import load_special_groups, special_group_index
from .regions import compute_all_regions
from .contribution import rel_weight


def build_web_bundle(result: CPIResult) -> dict[str, Any]:
    months = [m["period"] for m in result.months]
    names = {n.row: (n.name or str(n.row)) for n in result.structure}
    groups_cfg = load_special_groups()
    labels = groups_cfg["labels_mn"]
    group_members = groups_cfg["groups"]
    group_order = groups_cfg.get("order") or list(group_members.keys())
    n = len(months)

    def pack_scope(weights: dict[int, float], indices: dict[int, list[float]]):
        total = weights.get(8, 0.0) or 0.0
        groups = {}
        for row in MAJOR_ROWS:
            series = indices.get(row, [100.0] * n)
            w_abs = weights.get(row, 0.0) or 0.0
            w_rel = (w_abs / total * 100.0) if total else 0.0
            if row == 8:
                w_rel = 100.0
            groups[str(row)] = {
                "name": names.get(row, str(row)),
                "weight": round(w_rel, 6),
                "weight_abs": w_abs,
                "indices": [round(x, 6) for x in series],
            }
        return {
            "weight_total": total,
            "overall": [round(x, 6) for x in indices.get(8, [100.0] * n)],
            "groups": groups,
        }

    # Special series
    def pack_special(weights, indices):
        total = weights.get(8, 0.0) or 0.0
        out = {}
        # stable order: config order first, then any extras
        keys = list(group_order)
        for k in group_members:
            if k not in keys:
                keys.append(k)
        for key in keys:
            members = group_members.get(key)
            if not members:
                continue
            series, abs_w = special_group_index(members, weights, indices, n)
            w_rel = (abs_w / total * 100.0) if total else 0.0
            out[key] = {
                "label": labels.get(key, key),
                "weight": round(w_rel, 6),
                "n_items": sum(
                    1
                    for r in members
                    if (weights.get(r, 0.0) or 0.0) > 0 and r in indices
                ),
                "indices": [round(x, 6) for x in series],
            }
        return out

    nat = pack_scope(result.national.weights, result.national.indices)
    ub = None
    if "20" in result.regions:
        rr = result.regions["20"]
        ub = pack_scope(rr.weights, rr.indices)

    aimags = {}
    for code in sorted(result.regions.keys()):
        rr = result.regions[code]
        aimags[code] = {
            "name": rr.name,
            "weight": round(rr.weights.get(8, 0.0) or 0.0, 6),
            "overall": [round(x, 6) for x in rr.overall],
        }

    special = {
        "national": pack_special(result.national.weights, result.national.indices),
    }
    if "20" in result.regions:
        ubr = result.regions["20"]
        special["ulaanbaatar"] = pack_special(ubr.weights, ubr.indices)

    regional = compute_all_regions(result)
    regions_out: dict[str, Any] = {}
    for scheme, regs in regional.items():
        regions_out[scheme] = {}
        for name, agg in regs.items():
            regions_out[scheme][name] = {
                "codes": agg["codes"],
                "weight": round(agg["weight_total"], 6),
                "overall": [round(x, 6) for x in agg["overall"]],
            }

    return {
        "base_year": result.base_year,
        "generated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "months": months,
        "national": nat,
        "ulaanbaatar": ub,
        "aimags": aimags,
        "special": special,
        "special_order": group_order,
        "regions": regions_out,
        "scopes_note": "Тусгай бүлэг зөвхөн Улс + Улаанбаатар",
    }


def export_web_bundle(result: CPIResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = build_web_bundle(result)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))
    return path
