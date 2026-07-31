"""Хугацаа (сар) — оролт, индекс, гарчиг."""

from __future__ import annotations

import re
from dataclasses import dataclass

ROMAN = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
    5: "V",
    6: "VI",
    7: "VII",
    8: "VIII",
    9: "IX",
    10: "X",
    11: "XI",
    12: "XII",
}

MONTH_MN = {
    1: "1",
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    10: "10",
    11: "11",
    12: "12",
}

MONTH_EN = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


@dataclass(frozen=True)
class Period:
    year: int
    month: int  # 1-12

    @property
    def key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def yyyymm(self) -> str:
        return f"{self.year:04d}{self.month:02d}"

    @property
    def roman(self) -> str:
        return f"{self.year} {ROMAN[self.month]}"

    def title_mn(self) -> str:
        return f"{self.year} оны {MONTH_MN[self.month]} дугаар сард"

    def title_en(self) -> str:
        return f"in {MONTH_EN[self.month]} {self.year}"

    def prev_month(self) -> "Period":
        if self.month == 1:
            return Period(self.year - 1, 12)
        return Period(self.year, self.month - 1)

    def same_month_prev_year(self) -> "Period":
        return Period(self.year - 1, self.month)

    def end_prev_year(self) -> "Period":
        """Өмнөх оны эцэс = өмнөх оны 12-р сар."""
        return Period(self.year - 1, 12)


def parse_period(text: str) -> Period:
    """
    Зөвшөөрөх формат:
      2026-06, 2026.06, 2026/06, 202606, 2026 6, 2026 VI
    """
    s = text.strip().upper().replace("оны", " ").replace("ДУГААР", " ")
    s = re.sub(r"\s+", " ", s)

    m = re.match(r"^(\d{4})-(\d{1,2})$", s)
    if m:
        return Period(int(m.group(1)), int(m.group(2)))

    m = re.match(r"^(\d{4})[./](\d{1,2})$", s)
    if m:
        return Period(int(m.group(1)), int(m.group(2)))

    m = re.match(r"^(\d{4})(\d{2})$", s)
    if m:
        return Period(int(m.group(1)), int(m.group(2)))

    roman_map = {v: k for k, v in ROMAN.items()}
    m = re.match(r"^(\d{4})\s+([IVX]+)$", s)
    if m and m.group(2) in roman_map:
        return Period(int(m.group(1)), roman_map[m.group(2)])

    m = re.match(r"^(\d{4})\s+(\d{1,2})$", s)
    if m:
        return Period(int(m.group(1)), int(m.group(2)))

    raise ValueError(
        f"Хугацаа танигдсангүй: {text!r}. Жишээ: 2026-06, 2026.06, 202606"
    )


def period_index(periods: list[dict], p: Period) -> int:
    """months.json-ийн period жагсаалтаас индекс (0-based)."""
    key = p.key
    for i, m in enumerate(periods):
        if m.get("period") == key:
            return i
    # try label match 2026.06
    alt = f"{p.year}.{p.month:02d}"
    for i, m in enumerate(periods):
        lab = str(m.get("label", ""))
        if lab.startswith(alt):
            return i
    raise KeyError(f"Хугацаа өгөгдөлд алга: {key}. Боломжтой: {periods[0]['period']} … {periods[-1]['period']}")


def latest_period(periods: list[dict], overall: list[float] | None = None) -> Period:
    """Сүүлийн 'идэвхтэй' сар (индекс 100-аас зөрсөн) эсвэл жагсаалтын сүүл."""
    if overall:
        for i in range(len(overall) - 1, -1, -1):
            if abs(overall[i] - 100.0) > 1e-6:
                y, m = periods[i]["period"].split("-")
                return Period(int(y), int(m))
    y, m = periods[-1]["period"].split("-")
    return Period(int(y), int(m))


def pct_change(cur: float, base: float) -> float | None:
    """(cur/base)*100 - 100  — Excel BD/BE/BF томьёо."""
    if base is None or base == 0 or cur is None:
        return None
    return (cur / base) * 100.0 - 100.0


def three_way_changes(
    series: list[float],
    t: int,
) -> dict[str, float | None]:
    """
    t = одоогийн сарын индекс (0-based).

    yoy  — өмнөх оны мөн үе (t-12)
    ytd  — өмнөх оны эцэс (12-р сар): t-ийн жилийн өмнөх 12-р сар
    mom  — өмнөх сар (t-1)
    """
    if t < 0 or t >= len(series):
        return {"yoy": None, "ytd": None, "mom": None, "index": None}

    cur = series[t]
    yoy = pct_change(cur, series[t - 12]) if t >= 12 else None
    mom = pct_change(cur, series[t - 1]) if t >= 1 else None

    # year-end: December of previous calendar year
    # if months start at 2023-01 (t=0), period at t is year = 2023 + t//12, month = t%12+1
    year = 2023 + t // 12
    # Dec of year-1: month index for (year-1)-12 = ((year-1)-2023)*12 + 11
    dec_t = ((year - 1) - 2023) * 12 + 11
    ytd = pct_change(cur, series[dec_t]) if 0 <= dec_t < len(series) else None

    return {"yoy": yoy, "ytd": ytd, "mom": mom, "index": cur}
