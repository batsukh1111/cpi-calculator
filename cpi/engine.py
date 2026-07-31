"""
CPI тооцооллын цөм.

Аргачлал (Excel-тэй ижил):
1. Суурь үнэ P0 = 2023 оны 12 сарын дундаж үнэ
2. Барааны (elementary) индекс — short-term chain:
     t=0 (эхний сар):  I_t = (P_t / P0) * 100   хэрэв P_t≠0 else 100
     t>0:              I_t = (P_t / P_{t-1}) * I_{t-1}  хэрэв P_t≠0 else 100
3. Анги/бүлэг: жигнэсэн дундаж
     I_parent = Σ (w_i * I_i) / w_parent
     w_i = харьцангуй жин = H_i / H_total * 100
4. Улсын индекс: аймгуудын жингээр
     I_nat = Σ (H_aimag * I_aimag) / Σ H_aimag
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .loader import Node, RegionData, WorkbookData


@dataclass
class RegionResult:
    code: str
    name: str
    weights: dict[int, float]
    rel_weights: dict[int, float]  # I = H/H8*100
    indices: dict[int, list[float]]  # row -> list of monthly indices
    base_prices: dict[int, float | None]  # price_row -> P0
    # major group convenience
    overall: list[float] = field(default_factory=list)


@dataclass
class NationalResult:
    weights: dict[int, float]  # sum of aimag H
    indices: dict[int, list[float]]
    overall: list[float] = field(default_factory=list)


@dataclass
class CPIResult:
    months: list[dict[str, Any]]
    structure: list[Node]
    regions: dict[str, RegionResult]
    national: NationalResult
    base_year: int = 2023


class CPICalculator:
    """Excel-ийн томьёог Python-д шилжүүлсэн тооцоолуур."""

    def __init__(self, data: WorkbookData):
        self.data = data
        self.structure = data.structure
        self.by_row = data.nodes_by_row
        self.months = data.months
        self.n_months = len(data.months)
        self.base_n = data.base_month_count  # first 12 months of series = 2023

    # ------------------------------------------------------------------
    # Relative weights
    # ------------------------------------------------------------------
    def relative_weights(self, weights: dict[int, float]) -> dict[int, float]:
        total = weights.get(8, 0.0) or 0.0
        if total == 0:
            return {r: 0.0 for r in weights}
        return {r: (w / total) * 100.0 for r, w in weights.items()}

    # ------------------------------------------------------------------
    # Elementary index (chain)
    # ------------------------------------------------------------------
    def base_price(self, month_prices: list[float | None]) -> float | None:
        """P0 = AVERAGE of base-year months (first 12), Excel AVERAGE (хоосон нүд алгасна)."""
        base_vals = [p for p in month_prices[: self.base_n] if p is not None]
        if not base_vals:
            base_vals = [p for p in month_prices if p is not None]
        if not base_vals:
            return None
        return sum(base_vals) / len(base_vals)

    def elementary_indices(
        self, month_prices: list[float | None], base: float | None
    ) -> list[float]:
        """
        Chain short-term relative indices, base period average = 100.
        Missing/zero price → 100 (Excel IF(price=0, 100, ...)).
        """
        n = len(month_prices)
        out = [100.0] * n
        if base is None or base == 0:
            return out

        prev_price: float | None = None
        prev_index = 100.0

        for t, p in enumerate(month_prices):
            if p is None or p == 0:
                out[t] = 100.0
                # Excel sets 100 and does not update chain from this month's price
                # Previous price for next month: formula uses P_t / P_{t-1} * I_{t-1}
                # If current is 0 → 100; next month still divides by this 0 cell?
                # Excel: L = IF(L_price=0, 100, L_price/K_price * K_index)
                # so prev_price stays as the actual cell value (0) — but then next
                # non-zero would divide by 0. In practice missing months stay empty
                # and items with gaps often have continuous prices. We keep last
                # valid price for robustness when price returns.
                continue

            if t == 0 or prev_price is None or prev_price == 0:
                # first valid or after gap: link to base
                idx = (p / base) * 100.0
            else:
                idx = (p / prev_price) * prev_index

            out[t] = idx
            prev_price = p
            prev_index = idx

        return out

    # ------------------------------------------------------------------
    # Aggregate bottom-up
    # ------------------------------------------------------------------
    def aggregate_region(self, region: RegionData) -> RegionResult:
        weights = region.weights
        rel = self.relative_weights(weights)
        indices: dict[int, list[float]] = {}
        base_prices: dict[int, float | None] = {}

        # 1) Elementary items
        for node in self.structure:
            if node.kind != "elementary":
                continue
            pr = node.price_row
            if pr is None:
                indices[node.row] = [100.0] * self.n_months
                continue
            prices = region.prices.get(pr, [None] * self.n_months)
            # pad
            if len(prices) < self.n_months:
                prices = list(prices) + [None] * (self.n_months - len(prices))
            bp = self.base_price(prices)
            base_prices[pr] = bp
            indices[node.row] = self.elementary_indices(prices, bp)

        # 2) Bottom-up: process rows in reverse so children are ready
        # Structure is top-down; children always have higher row numbers for
        # sumproduct ranges, and for weighted_children children rows are deeper.
        # Safe order: reverse row order.
        for node in sorted(self.structure, key=lambda n: n.row, reverse=True):
            if node.kind == "elementary":
                continue
            if node.kind in ("sumproduct", "weighted_children"):
                indices[node.row] = self._weighted_avg(
                    node, rel, indices, weights
                )
            else:
                indices[node.row] = [100.0] * self.n_months

        overall = indices.get(8, [100.0] * self.n_months)

        return RegionResult(
            code=region.code,
            name=region.name,
            weights=weights,
            rel_weights=rel,
            indices=indices,
            base_prices=base_prices,
            overall=list(overall),
        )

    def _weighted_avg(
        self,
        node: Node,
        rel: dict[int, float],
        indices: dict[int, list[float]],
        weights: dict[int, float],
    ) -> list[float]:
        parent_w = rel.get(node.row, 0.0)
        children = node.children
        out = [100.0] * self.n_months

        if parent_w == 0:
            return out

        for t in range(self.n_months):
            s = 0.0
            for c in children:
                wi = rel.get(c, 0.0)
                ii = indices.get(c)
                if ii is None:
                    continue
                s += wi * ii[t]
            out[t] = s / parent_w
        return out

    # ------------------------------------------------------------------
    # National
    # ------------------------------------------------------------------
    def national_from_regions(
        self, region_results: dict[str, RegionResult]
    ) -> NationalResult:
        codes = list(region_results.keys())
        nat_w: dict[int, float] = {}
        nat_idx: dict[int, list[float]] = {}

        rows = [n.row for n in self.structure]
        for row in rows:
            w_sum = 0.0
            for code in codes:
                w_sum += region_results[code].weights.get(row, 0.0)
            nat_w[row] = w_sum

            series = [100.0] * self.n_months
            if w_sum == 0:
                nat_idx[row] = series
                continue
            for t in range(self.n_months):
                s = 0.0
                for code in codes:
                    rr = region_results[code]
                    w = rr.weights.get(row, 0.0)
                    idx_list = rr.indices.get(row)
                    if idx_list is None:
                        continue
                    s += w * idx_list[t]
                series[t] = s / w_sum
            nat_idx[row] = series

        return NationalResult(
            weights=nat_w,
            indices=nat_idx,
            overall=list(nat_idx.get(8, [100.0] * self.n_months)),
        )

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------
    def calculate(self) -> CPIResult:
        region_results: dict[str, RegionResult] = {}
        for code, region in self.data.regions.items():
            region_results[code] = self.aggregate_region(region)
        national = self.national_from_regions(region_results)
        return CPIResult(
            months=self.months,
            structure=self.structure,
            regions=region_results,
            national=national,
            base_year=self.data.base_year,
        )


def inflation_mom(indices: list[float]) -> list[float | None]:
    """Month-over-month % change."""
    out: list[float | None] = [None]
    for t in range(1, len(indices)):
        if indices[t - 1] == 0:
            out.append(None)
        else:
            out.append((indices[t] / indices[t - 1] - 1.0) * 100.0)
    return out


def inflation_yoy(indices: list[float], lag: int = 12) -> list[float | None]:
    """Year-over-year % change."""
    out: list[float | None] = []
    for t in range(len(indices)):
        if t < lag or indices[t - lag] == 0:
            out.append(None)
        else:
            out.append((indices[t] / indices[t - lag] - 1.0) * 100.0)
    return out
