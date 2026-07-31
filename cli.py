#!/usr/bin/env python3
"""
CPI тооцооллын командын мөр.

Жишээ:
  python cli.py calculate -i "cpi calculation 2023=100.xlsx" -o output/
  python cli.py calculate -i file.xlsx --aimag 01 20 --json
  python cli.py validate -i file.xlsx
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# allow running without install
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cpi.loader import load_workbook_data
from cpi.engine import CPICalculator, inflation_yoy
from cpi.export import export_excel, export_json, export_overall_csv


def cmd_calculate(args: argparse.Namespace) -> int:
    excel = Path(args.input)
    if not excel.exists():
        print(f"Файл олдсонгүй: {excel}", file=sys.stderr)
        return 1

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    aimag_codes = args.aimag
    print(f"Уншиж байна: {excel}")
    t0 = time.perf_counter()
    data = load_workbook_data(excel, aimag_codes=aimag_codes)
    print(
        f"  Аймаг: {len(data.regions)}, сар: {len(data.months)}, "
        f"мөр: {len(data.structure)} ({time.perf_counter()-t0:.1f}s)"
    )

    print("Тооцоолж байна...")
    t1 = time.perf_counter()
    calc = CPICalculator(data)
    result = calc.calculate()
    print(f"  Дууслаа ({time.perf_counter()-t1:.1f}s)")

    # Print latest overall
    last_i = len(result.months) - 1
    # find last non-empty-looking month (has variation from 100 or any prices)
    while last_i > 0 and result.national.overall[last_i] == 100.0:
        # could be real 100; check a few regions for price activity
        break
    # better: last month with any aimag overall != 100 or has data
    for i in range(len(result.months) - 1, -1, -1):
        if abs(result.national.overall[i] - 100.0) > 1e-9 or i < 12:
            last_i = i
            # keep scanning for actual last with prices — use max month that any region differs
            break
    # find rightmost month where national is not exactly default unused
    last_i = len(result.months) - 1
    for i in range(len(result.months) - 1, -1, -1):
        vals = [result.regions[c].overall[i] for c in result.regions]
        if any(abs(v - 100.0) > 1e-6 for v in vals) or any(
            abs(v - 100.0) > 1e-6 for v in [result.national.overall[i]]
        ):
            last_i = i
            break

    period = result.months[last_i]["period"]
    overall = result.national.overall[last_i]
    yoy = inflation_yoy(result.national.overall)
    yoy_v = yoy[last_i]
    print()
    print(f"=== Улсын ерөнхий индекс ({period}) ===")
    print(f"  Индекс (2023=100): {overall:.2f}")
    if yoy_v is not None:
        print(f"  Жилийн инфляц:     {yoy_v:.2f}%")
    print()
    print("Аймаг / нийслэл (сүүлийн сар):")
    for code in sorted(result.regions.keys()):
        rr = result.regions[code]
        print(f"  {code} {rr.name:14s}  {rr.overall[last_i]:8.2f}  жин={rr.weights.get(8,0):.3f}")

    if args.excel or not args.json_only:
        xlsx_path = out / "cpi_result.xlsx"
        export_excel(result, xlsx_path)
        print(f"\nExcel: {xlsx_path}")

    if args.json or args.json_only:
        json_path = out / "cpi_result.json"
        export_json(result, json_path, compact=not args.full_json)
        print(f"JSON:  {json_path}")

    csv_path = out / "cpi_overall.csv"
    export_overall_csv(result, csv_path)
    print(f"CSV:   {csv_path}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Excel-ийн data_only утгатай харьцуулах."""
    import openpyxl

    excel = Path(args.input)
    print(f"Тооцоолж байна: {excel}")
    data = load_workbook_data(excel)
    result = CPICalculator(data).calculate()

    print("Excel-ийн хадгалагдсан утгуудыг уншиж байна (data_only)...")
    wb = openpyxl.load_workbook(excel, data_only=True, read_only=True)

    def col_for_month(mi: int) -> int:
        return 11 + mi  # K=11

    max_check_months = min(24, len(result.months))  # first 2 years
    check_rows = [8, 9, 10, 11, 12, 13, 18, 209, 316]

    total = 0
    mismatches = 0
    max_diff = 0.0

    for code in ["01", "20"]:
        if code not in wb.sheetnames or code not in result.regions:
            continue
        ws = wb[code]
        rr = result.regions[code]
        print(f"\n--- Sheet {code} ({rr.name}) ---")
        for row in check_rows:
            for mi in range(max_check_months):
                excel_val = ws.cell(row, col_for_month(mi)).value
                if excel_val is None:
                    continue
                try:
                    excel_f = float(excel_val)
                except (TypeError, ValueError):
                    continue
                our = rr.indices[row][mi]
                diff = abs(our - excel_f)
                total += 1
                max_diff = max(max_diff, diff)
                if diff > args.tol:
                    mismatches += 1
                    if mismatches <= 15:
                        print(
                            f"  DIFF {code} r{row} m{result.months[mi]['period']}: "
                            f"ours={our:.6f} excel={excel_f:.6f} Δ={diff:.6f}"
                        )

    # National
    if "base index national" in wb.sheetnames:
        ws = wb["base index national"]
        print("\n--- National ---")
        for row in check_rows:
            for mi in range(max_check_months):
                excel_val = ws.cell(row, col_for_month(mi)).value
                if excel_val is None:
                    continue
                try:
                    excel_f = float(excel_val)
                except (TypeError, ValueError):
                    continue
                our = result.national.indices[row][mi]
                diff = abs(our - excel_f)
                total += 1
                max_diff = max(max_diff, diff)
                if diff > args.tol:
                    mismatches += 1
                    if mismatches <= 25:
                        print(
                            f"  DIFF NAT r{row} m{result.months[mi]['period']}: "
                            f"ours={our:.6f} excel={excel_f:.6f} Δ={diff:.6f}"
                        )

    wb.close()
    print(f"\nШалгасан: {total}, зөрүү (>{args.tol}): {mismatches}, max|Δ|={max_diff:.8f}")
    if mismatches == 0:
        print("OK — Excel-тэй таарч байна.")
        return 0
    print("АНХААР: зөрүү олдлоо.")
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Хэрэглээний үнийн индекс (CPI) тооцоолуур — 2023=100"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("calculate", help="Индекс тооцоод файлд хадгалах")
    c.add_argument("-i", "--input", required=True, help="cpi calculation Excel файл")
    c.add_argument("-o", "--output", default="output", help="гаралтын хавтас")
    c.add_argument(
        "--aimag",
        nargs="+",
        default=None,
        help="Зөвхөн эдгээр аймгууд (жишээ: 01 20). Хоосон=бүгд",
    )
    c.add_argument("--json", action="store_true", help="JSON экспорт нэмэх")
    c.add_argument("--json-only", action="store_true", help="Зөвхөн JSON")
    c.add_argument("--full-json", action="store_true", help="Бүх мөрийн индекс JSON-д")
    c.add_argument("--excel", action="store_true", default=True)
    c.set_defaults(func=cmd_calculate)

    v = sub.add_parser("validate", help="Excel-ийн утгатай харьцуулах")
    v.add_argument("-i", "--input", required=True)
    v.add_argument("--tol", type=float, default=0.01, help="зөвшөөрөгдөх зөрүү")
    v.set_defaults(func=cmd_validate)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
