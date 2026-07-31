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
    default_compare_periods,
    resolve_compare_indices,
    Period,
)
from cpi.special_groups import compute_ub_and_national_special
from cpi.regions import compute_all_regions
from cpi.publication import generate_publication
from cpi.contribution import compute_contributions

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
    "loading": False,
    "load_error": None,
}


def _ensure_output():
    OUTPUT.mkdir(parents=True, exist_ok=True)


def _run_calculate(excel: Path | None = None):
    excel = Path(excel or DEFAULT_EXCEL)
    if not excel.exists():
        raise FileNotFoundError(f"Excel олдсонгүй: {excel}")
    CACHE["loading"] = True
    CACHE["load_error"] = None
    try:
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
    except Exception as e:
        CACHE["load_error"] = str(e)
        raise
    finally:
        CACHE["loading"] = False


def _get_result():
    if CACHE["result"] is None:
        return None, None
    return CACHE["result"], CACHE["data"]


def _ch(series, t, cmp_idx=None):
    if cmp_idx is None:
        return three_way_changes(series, t)
    return three_way_changes(
        series,
        t,
        t_yoy=cmp_idx.get("yoy"),
        t_ytd=cmp_idx.get("ytd"),
        t_mom=cmp_idx.get("mom"),
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    ready = CACHE["result"] is not None
    return jsonify(
        {
            "ready": ready,
            "loading": bool(CACHE.get("loading")),
            "load_error": CACHE.get("load_error"),
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
        try:
            period = parse_period(period_s)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    else:
        period = latest_period(result.months, result.national.overall)

    try:
        t = period_index(result.months, period)
    except KeyError as e:
        return jsonify({"error": str(e)}), 400

    # Чөлөөт харьцуулах сар (хоосон = стандарт)
    vs_yoy = request.args.get("vs_yoy") or request.args.get("cmp1")
    vs_ytd = request.args.get("vs_ytd") or request.args.get("cmp2")
    vs_mom = request.args.get("vs_mom") or request.args.get("cmp3")
    try:
        cmp_idx, cmp_labels = resolve_compare_indices(
            result.months, period, vs_yoy, vs_ytd, vs_mom
        )
    except ValueError as e:
        return jsonify({"error": f"Харьцуулах сар буруу: {e}"}), 400

    defaults = default_compare_periods(period)

    nat = _ch(result.national.overall, t, cmp_idx)
    aimags = []
    for code in sorted(result.regions.keys()):
        rr = result.regions[code]
        c = _ch(rr.overall, t, cmp_idx)
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
        c = _ch(series, t, cmp_idx)
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
            c_ub = _ch(g_ub["indices"], t, cmp_idx)
            c_nat = _ch(g_nat["indices"], t, cmp_idx)
            special.append(
                {
                    "key": key,
                    "label": g_ub["label_mn"],
                    "ub_index": c_ub["index"],
                    "ub_yoy": c_ub["yoy"],
                    "ub_ytd": c_ub["ytd"],
                    "ub_mom": c_ub["mom"],
                    "nat_index": c_nat["index"],
                    "nat_yoy": c_nat["yoy"],
                    "nat_ytd": c_nat["ytd"],
                    "nat_mom": c_nat["mom"],
                }
            )

    regional = compute_all_regions(result)
    regions_out = {}
    for scheme, regs in regional.items():
        regions_out[scheme] = []
        for name, agg in regs.items():
            c = _ch(agg["overall"], t, cmp_idx)
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
    # chart: % vs first custom compare (yoy slot)
    chart_vs = []
    t_base = cmp_idx.get("yoy")
    for i, val in enumerate(nat_series):
        if t_base is not None and t_base < len(nat_series) and nat_series[t_base]:
            # fixed base period change over time from that base? better: rolling yoy style
            pass
        chart_vs.append(inflation_yoy(nat_series)[i])

    # write comparison csv for download
    _ensure_output()
    import csv

    csv_path = OUTPUT / f"comparison_{period.yyyymm}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "code",
                "name",
                "index",
                f"vs_{cmp_labels['yoy']}_pct",
                f"vs_{cmp_labels['ytd']}_pct",
                f"vs_{cmp_labels['mom']}_pct",
            ]
        )
        w.writerow(["00", "Улс", nat["index"], nat["yoy"], nat["ytd"], nat["mom"]])
        for a in aimags:
            w.writerow(
                [a["code"], a["name"], a["index"], a["yoy"], a["ytd"], a["mom"]]
            )

    # Инфляцын оролцоо — 3 харьцуулалт бүрт
    contrib = {}
    for slot, label in [
        ("yoy", cmp_labels["yoy"]),
        ("ytd", cmp_labels["ytd"]),
        ("mom", cmp_labels["mom"]),
    ]:
        tb = cmp_idx.get(slot)
        if tb is not None:
            contrib[slot] = compute_contributions(result, t, tb, base_label=label)
        else:
            contrib[slot] = None

    return jsonify(
        {
            "period": period.key,
            "period_label": period.title_mn(),
            "period_en": period.title_en(),
            "roman": period.roman,
            "compare": {
                "yoy": cmp_labels["yoy"],
                "ytd": cmp_labels["ytd"],
                "mom": cmp_labels["mom"],
                "defaults": {
                    "yoy": defaults["yoy"].key,
                    "ytd": defaults["ytd"].key,
                    "mom": defaults["mom"].key,
                },
            },
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
            "contribution": contrib,
            "series": {
                "months": months,
                "national": nat_series,
                "ub": ub_series,
                "national_yoy": chart_vs,
            },
            "available_months": months,
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


def _preload_async():
    """Excel тооцоог ард ажиллуулна — вeb шууд нээгдэнэ."""
    import threading

    def job():
        if not DEFAULT_EXCEL.exists():
            print("  Excel MISSING — вeb нээгдэнэ, «Excel дахин» дарна уу.")
            return
        if CACHE["result"] is not None:
            return
        print("  Background: Excel уншиж байна (30-90 sec)...")
        try:
            _run_calculate()
            print("  Background: DONE — data ready.")
        except Exception as e:
            print(f"  Background ERROR: {e}")

    threading.Thread(target=job, daemon=True).start()


def main():
    _ensure_output()
    print("=" * 50)
    print("  CPI WEB")
    print("  Open: http://127.0.0.1:5050")
    print("=" * 50)
    print(f"  Excel:    {DEFAULT_EXCEL} ({'OK' if DEFAULT_EXCEL.exists() else 'MISSING'})")
    print(
        f"  Template: {DEFAULT_TEMPLATE} ({'OK' if DEFAULT_TEMPLATE.exists() else 'MISSING'})"
    )
    print("  Server starting NOW (page opens immediately)...")
    _preload_async()
    # use_reloader=False so Windows double-start does not break
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
