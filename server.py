#!/usr/bin/env python3
"""
CPI веб сервер (Flask).

Ажиллуулах:
  python server.py
  → http://127.0.0.1:5050
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    abort,
)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cpi.loader import load_workbook_data, load_aimags
from cpi.engine import CPICalculator, inflation_yoy
from cpi.export import export_excel, export_overall_csv, MAJOR_ROWS
from cpi.period import (
    parse_period,
    latest_period,
    period_index,
    three_way_changes,
    Period,
)
from cpi.special_groups import compute_ub_and_national_special
from cpi.regions import compute_all_regions
from cpi.publication import generate_publication

app = Flask(
    __name__,
    template_folder=str(ROOT / "web" / "templates"),
    static_folder=str(ROOT / "web" / "static"),
)

# ---------- config ----------
DEFAULT_EXCEL = Path(r"C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx")
DEFAULT_TEMPLATE = Path(r"C:\Users\batsukh\Desktop\National_202607_2023.xlsx")
OUTPUT = ROOT / "output"
CACHE = {
    "result": None,
    "data": None,
    "loaded_at": None,
    "excel": None,
}


def _ensure_output():
    OUTPUT.mkdir(parents=True, exist_ok=True)


def _run_calculate(excel: Path | None = None):
    excel = Path(excel or DEFAULT_EXCEL)
    if not excel.exists():
        raise FileNotFoundError(f"Excel олдсонгүй: {excel}")
    t0 = time.perf_counter()
    data = load_workbook_data(excel)
    result = CPICalculator(data).calculate()
    elapsed = time.perf_counter() - t0
    CACHE["result"] = result
    CACHE["data"] = data
    CACHE["loaded_at"] = time.time()
    CACHE["excel"] = str(excel)
    _ensure_output()
    export_excel(result, OUTPUT / "cpi_result.xlsx")
    export_overall_csv(result, OUTPUT / "cpi_overall.csv")
    return result, data, elapsed


def _get_result():
    if CACHE["result"] is None:
        # try load from existing calculation if excel available
        if DEFAULT_EXCEL.exists():
            _run_calculate()
        else:
            return None, None
    return CACHE["result"], CACHE["data"]


def _ch(series, t):
    return three_way_changes(series, t)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    ready = CACHE["result"] is not None
    return jsonify(
        {
            "ready": ready,
            "excel": CACHE.get("excel"),
            "loaded_at": CACHE.get("loaded_at"),
            "default_excel_exists": DEFAULT_EXCEL.exists(),
            "template_exists": DEFAULT_TEMPLATE.exists(),
        }
    )


@app.route("/api/periods")
def api_periods():
    result, _ = _get_result()
    if result is None:
        return jsonify({"ready": False, "periods": [], "default": None})
    periods = [m["period"] for m in result.months]
    default = latest_period(result.months, result.national.overall).key
    return jsonify({"ready": True, "periods": periods, "default": default})


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    try:
        body = request.get_json(silent=True) or {}
        excel = body.get("excel") or str(DEFAULT_EXCEL)
        result, data, elapsed = _run_calculate(Path(excel))
        return jsonify(
            {
                "ok": True,
                "seconds": elapsed,
                "months": len(result.months),
                "aimags": len(result.regions),
            }
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard")
def api_dashboard():
    result, data = _get_result()
    if result is None:
        return jsonify({"error": "Тооцоолол хийгээгүй. «Дахин тооцоолох» дарна уу."}), 400

    period_s = request.args.get("period")
    if period_s:
        period = parse_period(period_s)
    else:
        period = latest_period(result.months, result.national.overall)

    try:
        t = period_index(result.months, period)
    except KeyError as e:
        return jsonify({"error": str(e)}), 400

    nat = _ch(result.national.overall, t)
    aimags = []
    for code in sorted(result.regions.keys()):
        rr = result.regions[code]
        c = _ch(rr.overall, t)
        aimags.append(
            {
                "code": code,
                "name": rr.name,
                "weight": rr.weights.get(8, 0.0),
                "index": c["index"],
                "yoy": c["yoy"],
                "ytd": c["ytd"],
                "mom": c["mom"],
            }
        )

    by_row = {n.row: n for n in result.structure}
    groups = []
    for row in MAJOR_ROWS:
        node = by_row.get(row)
        series = result.national.indices.get(row, [])
        c = _ch(series, t)
        groups.append(
            {
                "row": row,
                "name": node.name if node else str(row),
                "weight": result.national.weights.get(row, 0.0),
                "index": c["index"],
                "yoy": c["yoy"],
                "ytd": c["ytd"],
                "mom": c["mom"],
            }
        )

    special = []
    if "20" in result.regions:
        sp = compute_ub_and_national_special(result)
        for key, g_ub in sp["ulaanbaatar"].items():
            g_nat = sp["national"][key]
            special.append(
                {
                    "key": key,
                    "label": g_ub["label_mn"],
                    "ub_index": g_ub["indices"][t],
                    "ub_yoy": g_ub["yoy"][t],
                    "nat_index": g_nat["indices"][t],
                    "nat_yoy": g_nat["yoy"][t],
                }
            )

    regional = compute_all_regions(result)
    regions_out = {}
    for scheme, regs in regional.items():
        regions_out[scheme] = []
        for name, agg in regs.items():
            c = _ch(agg["overall"], t)
            regions_out[scheme].append(
                {
                    "name": name,
                    "codes": ",".join(agg["codes"]),
                    "weight": agg["weight_total"],
                    "index": c["index"],
                    "yoy": c["yoy"],
                    "ytd": c["ytd"],
                    "mom": c["mom"],
                }
            )

    months = [m["period"] for m in result.months]
    nat_series = result.national.overall
    ub_series = (
        result.regions["20"].overall
        if "20" in result.regions
        else [100.0] * len(months)
    )
    nat_yoy = inflation_yoy(nat_series)

    # write comparison csv for download
    _ensure_output()
    import csv

    csv_path = OUTPUT / f"comparison_{period.yyyymm}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "index", "yoy_pct", "ytd_pct", "mom_pct"])
        w.writerow(["00", "Улс", nat["index"], nat["yoy"], nat["ytd"], nat["mom"]])
        for a in aimags:
            w.writerow(
                [a["code"], a["name"], a["index"], a["yoy"], a["ytd"], a["mom"]]
            )

    return jsonify(
        {
            "period": period.key,
            "period_label": period.title_mn(),
            "period_en": period.title_en(),
            "roman": period.roman,
            "national": {
                "index": nat["index"],
                "yoy": nat["yoy"],
                "ytd": nat["ytd"],
                "mom": nat["mom"],
            },
            "aimags": aimags,
            "groups": groups,
            "special": special,
            "regions": regions_out,
            "series": {
                "months": months,
                "national": nat_series,
                "ub": ub_series,
                "national_yoy": nat_yoy,
            },
        }
    )


@app.route("/api/publish", methods=["POST"])
def api_publish():
    result, data = _get_result()
    if result is None or data is None:
        return jsonify({"error": "Эхлээд тооцоолол хийнэ үү."}), 400
    if not DEFAULT_TEMPLATE.exists():
        return jsonify(
            {"error": f"Загвар олдсонгүй: {DEFAULT_TEMPLATE}"}
        ), 400

    period_s = request.args.get("period") or (request.get_json(silent=True) or {}).get(
        "period"
    )
    if period_s:
        period = parse_period(period_s)
    else:
        period = latest_period(result.months, result.national.overall)

    _ensure_output()
    out = OUTPUT / f"National_{period.yyyymm}_2023.xlsx"
    try:
        generate_publication(
            result, data, period, DEFAULT_TEMPLATE, out, tables_only=True
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True, "filename": out.name, "path": str(out)})


@app.route("/api/download/publication")
def dl_publication():
    period_s = request.args.get("period")
    if not period_s:
        abort(400)
    period = parse_period(period_s)
    path = OUTPUT / f"National_{period.yyyymm}_2023.xlsx"
    if not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=path.name)


@app.route("/api/download/result")
def dl_result():
    path = OUTPUT / "cpi_result.xlsx"
    if not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=path.name)


@app.route("/api/download/comparison")
def dl_comparison():
    period_s = request.args.get("period")
    if period_s:
        period = parse_period(period_s)
        path = OUTPUT / f"comparison_{period.yyyymm}.csv"
    else:
        # latest comparison file
        files = sorted(OUTPUT.glob("comparison_*.csv"))
        path = files[-1] if files else None
    if not path or not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=path.name)


def main():
    _ensure_output()
    print("=" * 50)
    print("  CPI веб сайт")
    print("  http://127.0.0.1:5050")
    print("=" * 50)
    print(f"  Excel:   {DEFAULT_EXCEL} ({'OK' if DEFAULT_EXCEL.exists() else 'MISSING'})")
    print(
        f"  Template:{DEFAULT_TEMPLATE} ({'OK' if DEFAULT_TEMPLATE.exists() else 'MISSING'})"
    )
    # Preload in background-ish: optional auto calc
    if DEFAULT_EXCEL.exists() and CACHE["result"] is None:
        print("  Анхны тооцоолол эхэлж байна (30–90 сек)...")
        try:
            _run_calculate()
            print("  Бэлэн.")
        except Exception as e:
            print(f"  Анхны тооцоолол алдаа: {e}")
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)


if __name__ == "__main__":
    main()
