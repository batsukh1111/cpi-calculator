#!/usr/bin/env python3
"""
CPI тооцооллын Streamlit веб апп.

Ажиллуулах:
  streamlit run app.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cpi.loader import load_workbook_data, load_aimags
from cpi.engine import CPICalculator, inflation_yoy, inflation_mom
from cpi.export import export_excel, export_json, MAJOR_ROWS
from cpi.special_groups import compute_ub_and_national_special
from cpi.regions import compute_all_regions

st.set_page_config(
    page_title="CPI тооцоолуур | 2023=100",
    page_icon="📈",
    layout="wide",
)

st.title("Хэрэглээний үнийн индекс (CPI)")
st.caption("Суурь жил 2023=100 · Аймаг → улсын жигнэсэн индекс · COICOP бүлэг")

with st.sidebar:
    st.header("Тохиргоо")
    uploaded = st.file_uploader(
        "Excel файл (cpi calculation 2023=100.xlsx)",
        type=["xlsx"],
    )
    default_path = st.text_input(
        "эсвэл локал зам",
        value=r"C:\Users\batsukh\Desktop\cpi calculation 2023=100.xlsx",
    )
    aimags_meta = load_aimags()
    all_codes = sorted(aimags_meta.keys())
    selected = st.multiselect(
        "Аймаг / нийслэл",
        options=all_codes,
        default=all_codes,
        format_func=lambda c: f"{c} — {aimags_meta.get(c, c)}",
    )
    run = st.button("Тооцоолох", type="primary", use_container_width=True)


@st.cache_data(show_spinner="Excel уншиж, индекс тооцоолж байна…")
def run_calc(file_bytes: bytes | None, path: str, codes: tuple[str, ...]):
    import tempfile

    if file_bytes:
        tmp = Path(tempfile.gettempdir()) / "cpi_upload.xlsx"
        tmp.write_bytes(file_bytes)
        excel = tmp
    else:
        excel = Path(path)
        if not excel.exists():
            raise FileNotFoundError(f"Файл олдсонгүй: {excel}")

    data = load_workbook_data(excel, aimag_codes=list(codes) if codes else None)
    result = CPICalculator(data).calculate()
    return result


if run or "cpi_result" in st.session_state:
    try:
        if run:
            fb = uploaded.getvalue() if uploaded else None
            result = run_calc(fb, default_path, tuple(selected))
            st.session_state["cpi_result"] = result
        else:
            result = st.session_state["cpi_result"]
    except Exception as e:
        st.error(f"Алдаа: {e}")
        st.stop()

    periods = [m["period"] for m in result.months]
    by_row = {n.row: n for n in result.structure}

    # Latest meaningful month
    last_i = len(periods) - 1
    for i in range(len(periods) - 1, -1, -1):
        if abs(result.national.overall[i] - 100.0) > 1e-6:
            last_i = i
            break

    c1, c2, c3, c4 = st.columns(4)
    overall = result.national.overall[last_i]
    yoy = inflation_yoy(result.national.overall)
    mom = inflation_mom(result.national.overall)
    c1.metric("Сар", periods[last_i])
    c2.metric("Улсын индекс", f"{overall:.2f}")
    c3.metric(
        "Жилийн инфляц",
        f"{yoy[last_i]:.2f}%" if yoy[last_i] is not None else "—",
    )
    c4.metric(
        "Сарын өөрчлөлт",
        f"{mom[last_i]:.2f}%" if mom[last_i] is not None else "—",
    )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Улс", "Аймгууд", "Бүлгээр", "Тусгай бүлэг", "Бүс", "Татах"]
    )

    with tab1:
        st.subheader("Улсын ерөнхий индекс")
        df_nat = pd.DataFrame(
            {
                "Сар": periods,
                "Индекс": result.national.overall,
                "Жилийн %": yoy,
                "Сарын %": mom,
            }
        )
        st.line_chart(df_nat.set_index("Сар")[["Индекс"]])
        st.dataframe(df_nat, use_container_width=True, height=360)

        st.subheader("COICOP бүлгүүд (улс)")
        rows = []
        for r in MAJOR_ROWS:
            node = by_row.get(r)
            series = result.national.indices.get(r, [])
            rows.append(
                {
                    "Бүлэг": node.name if node else r,
                    "Жин": round(result.national.weights.get(r, 0.0), 4),
                    f"Индекс {periods[last_i]}": round(series[last_i], 2)
                    if series
                    else None,
                    "Жилийн %": round(inflation_yoy(series)[last_i], 2)
                    if series and inflation_yoy(series)[last_i] is not None
                    else None,
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    with tab2:
        st.subheader("Аймаг / нийслэлийн ерөнхий индекс")
        recs = []
        for code in sorted(result.regions.keys()):
            rr = result.regions[code]
            recs.append(
                {
                    "Код": code,
                    "Нэр": rr.name,
                    "Жин": round(rr.weights.get(8, 0.0), 4),
                    "Индекс": round(rr.overall[last_i], 2),
                    "Жилийн %": round(inflation_yoy(rr.overall)[last_i], 2)
                    if inflation_yoy(rr.overall)[last_i] is not None
                    else None,
                }
            )
        df_a = pd.DataFrame(recs).sort_values("Индекс", ascending=False)
        st.dataframe(df_a, use_container_width=True, height=500)

        st.subheader("Харьцуулалт — цаг хугацааны шугам")
        pick = st.multiselect(
            "Аймаг сонгох",
            options=sorted(result.regions.keys()),
            default=["20", "01", "19", "21"][: min(4, len(result.regions))],
            format_func=lambda c: f"{c} {result.regions[c].name}",
        )
        chart = {"Улс": result.national.overall}
        for c in pick:
            chart[result.regions[c].name] = result.regions[c].overall
        st.line_chart(pd.DataFrame(chart, index=periods))

    with tab3:
        st.subheader("Бүлгийн индекс — нэгж сонголт")
        scope = st.selectbox(
            "Хамрах хүрээ",
            ["Улс"]
            + [f"{c} — {result.regions[c].name}" for c in sorted(result.regions)],
        )
        if scope == "Улс":
            src = result.national.indices
            wsrc = result.national.weights
        else:
            code = scope.split(" — ")[0]
            src = result.regions[code].indices
            wsrc = result.regions[code].weights

        group_labels = {
            r: (by_row[r].name if r in by_row else str(r)) for r in MAJOR_ROWS
        }
        g = st.selectbox(
            "Бүлэг",
            MAJOR_ROWS,
            format_func=lambda r: group_labels[r],
        )
        series = src.get(g, [])
        df_g = pd.DataFrame(
            {
                "Сар": periods,
                "Индекс": series,
                "Жилийн %": inflation_yoy(series),
            }
        )
        st.metric("Жин", f"{wsrc.get(g, 0):.4f}")
        st.line_chart(df_g.set_index("Сар")[["Индекс"]])
        st.dataframe(df_g, use_container_width=True)

    with tab4:
        st.subheader("Тусгай барааны бүлэг (УБ + Улс)")
        st.caption("Ангилал: Бүлэг.xlsx → барааны бүлэг")
        if "20" not in result.regions:
            st.warning("Улаанбаатар (20) сонгогдоогүй байна.")
        else:
            special = compute_ub_and_national_special(result)
            rows = []
            for key, g_ub in special["ulaanbaatar"].items():
                g_nat = special["national"][key]
                rows.append(
                    {
                        "Бүлэг": g_ub["label_mn"],
                        "УБ жин": round(g_ub["weight"], 4),
                        "УБ индекс": round(g_ub["indices"][last_i], 2),
                        "УБ жилийн %": round(g_ub["yoy"][last_i], 2)
                        if g_ub["yoy"][last_i] is not None
                        else None,
                        "Улс жин": round(g_nat["weight"], 4),
                        "Улс индекс": round(g_nat["indices"][last_i], 2),
                        "Улс жилийн %": round(g_nat["yoy"][last_i], 2)
                        if g_nat["yoy"][last_i] is not None
                        else None,
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            pick_g = st.selectbox(
                "График — бүлэг",
                list(special["ulaanbaatar"].keys()),
                format_func=lambda k: special["ulaanbaatar"][k]["label_mn"],
            )
            chart = {
                "Улаанбаатар": special["ulaanbaatar"][pick_g]["indices"],
                "Улс": special["national"][pick_g]["indices"],
            }
            st.line_chart(pd.DataFrame(chart, index=periods))

    with tab5:
        st.subheader("Бүсийн индекс")
        st.caption("Ангилал: Бүлэг.xlsx → бүс / Шинэ бүс")
        if len(result.regions) < 2:
            st.warning("Бүс тооцоход олон аймаг хэрэгтэй.")
        else:
            regional = compute_all_regions(result)
            scheme = st.radio(
                "Бүсийн схем",
                ["traditional", "new"],
                format_func=lambda s: "Уламжлалт" if s == "traditional" else "Шинэ бүс",
                horizontal=True,
            )
            recs = []
            chart = {}
            for name, agg in regional[scheme].items():
                y = inflation_yoy(agg["overall"])[last_i]
                recs.append(
                    {
                        "Бүс": name,
                        "Аймгууд": ",".join(agg["codes"]),
                        "Жин": round(agg["weight_total"], 4),
                        "Индекс": round(agg["overall"][last_i], 2),
                        "Жилийн %": round(y, 2) if y is not None else None,
                    }
                )
                chart[name] = agg["overall"]
            st.dataframe(pd.DataFrame(recs), use_container_width=True)
            st.line_chart(pd.DataFrame(chart, index=periods))

    with tab6:
        st.subheader("Үр дүн татах")
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            xp = Path(td) / "cpi_result.xlsx"
            jp = Path(td) / "cpi_result.json"
            export_excel(result, xp)
            export_json(result, jp)
            xbytes = xp.read_bytes()
            jbytes = jp.read_bytes()

        st.download_button(
            "Excel татах (.xlsx)",
            data=xbytes,
            file_name="cpi_result_2023base.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "JSON татах",
            data=jbytes,
            file_name="cpi_result.json",
            mime="application/json",
        )

else:
    st.info(
        "Зүүн талаас Excel файлаа сонгоод **Тооцоолох** дарна уу.\n\n"
        "Файлд аймгуудын **сарын дундаж үнэ**-г (доод хэсэг) оруулбал "
        "суурь индекс (2023=100) автоматаар бодогдоно."
    )
    st.markdown(
        """
### Аргачлал (товч)
1. **Суурь үнэ** — 2023 оны 12 сарын дундаж  
2. **Барааны индекс** — short-term chain: \\(I_t = \\frac{P_t}{P_{t-1}} \\cdot I_{t-1}\\)  
3. **COICOP бүлэг** — жингийн жигнэсэн дундаж  
4. **Улс** — аймгуудын жингээр: \\(I^{nat} = \\sum_a w_a I_a / \\sum_a w_a\\)

Бүсчилсэн тооцоог дараагийн хувилбарт нэмнэ.
"""
    )
