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
from .loader import WorkbookData


def build_web_bundle(
    result: CPIResult,
    data: WorkbookData | None = None,
) -> dict[str, Any]:
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

    # --- УБ үнэ оруулах (веб форм) ---
    ub_edit: dict[str, Any] | None = None
    if data is not None and "20" in data.regions and "20" in result.regions:
        ub_reg = data.regions["20"]
        ub_res = result.regions["20"]
        rel = ub_res.rel_weights
        products = []
        for node in result.structure:
            if node.kind != "elementary" or not node.price_row:
                continue
            prices = ub_reg.prices.get(node.price_row, [None] * n)
            # pad
            if len(prices) < n:
                prices = list(prices) + [None] * (n - len(prices))
            products.append(
                {
                    "row": node.row,
                    "price_row": node.price_row,
                    "name": node.name or f"row {node.row}",
                    "item_no": node.item_no,
                    "weight": round(rel.get(node.row, 0.0), 8),
                    "weight_abs": round(ub_reg.weights.get(node.row, 0.0) or 0.0, 8),
                    "prices": [
                        (round(p, 4) if isinstance(p, (int, float)) else None)
                        for p in prices[:n]
                    ],
                }
            )
        # hierarchy for browser re-aggregation
        structure_export = []
        for node in result.structure:
            structure_export.append(
                {
                    "row": node.row,
                    "name": node.name,
                    "kind": node.kind,
                    "children": list(node.children or []),
                    "price_row": node.price_row,
                    "weight": round(rel.get(node.row, 0.0), 8),
                }
            )
        # special members for UB
        special_members = {
            k: list(v) for k, v in group_members.items()
        }
        ub_edit = {
            "code": "20",
            "name": "Улаанбаатар",
            "base_n": 12,
            "products": products,
            "structure": structure_export,
            "special_members": special_members,
            "weight_total_abs": round(ub_reg.weights.get(8, 0.0) or 0.0, 8),
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
        "ub_edit": ub_edit,
    }


def export_web_bundle(
    result: CPIResult,
    path: str | Path,
    data: WorkbookData | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = build_web_bundle(result, data=data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))
    return path
