/* Static CPI dashboard — works on GitHub Pages (no server) */
let DATA = null;
let charts = {};
let _skip = false;
let _timer = null;

const $ = (id) => document.getElementById(id);

function showStatus(msg, type) {
  const el = $("status");
  el.className = "status show " + (type || "info");
  el.textContent = msg;
}

function fmt(n, d = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toFixed(d);
}

function pctClass(n) {
  if (n == null) return "";
  if (n > 0.05) return "pos";
  if (n < -0.05) return "neg";
  return "";
}

function pctCell(n) {
  const s = n == null ? "—" : (n > 0 ? "+" : "") + fmt(n, 1);
  return `<td class="${pctClass(n)}">${s}</td>`;
}

function normPeriod(s) {
  if (!s) return "";
  s = String(s).trim();
  let m = s.match(/^(\d{4})-(\d{1,2})$/);
  if (m) return m[1] + "-" + String(+m[2]).padStart(2, "0");
  m = s.match(/^(\d{4})[./](\d{1,2})$/);
  if (m) return m[1] + "-" + String(+m[2]).padStart(2, "0");
  m = s.match(/^(\d{4})(\d{2})$/);
  if (m) return m[1] + "-" + m[2];
  return s;
}

function monthIndex(p) {
  const i = DATA.months.indexOf(p);
  return i;
}

function defaultsFor(p) {
  const m = p.match(/^(\d{4})-(\d{2})$/);
  if (!m) return null;
  const y = +m[1], mo = +m[2];
  const pmo = mo === 1 ? 12 : mo - 1;
  const py = mo === 1 ? y - 1 : y;
  return {
    v1: `${y - 1}-${String(mo).padStart(2, "0")}`,
    v2: `${y - 1}-12`,
    v3: `${py}-${String(pmo).padStart(2, "0")}`,
  };
}

function pctChange(cur, base) {
  if (cur == null || base == null || base === 0) return null;
  return (cur / base) * 100 - 100;
}

function threeWay(series, t, t1, t2, t3) {
  const cur = series[t];
  return {
    index: cur,
    c1: t1 != null && t1 >= 0 ? pctChange(cur, series[t1]) : null,
    c2: t2 != null && t2 >= 0 ? pctChange(cur, series[t2]) : null,
    c3: t3 != null && t3 >= 0 ? pctChange(cur, series[t3]) : null,
  };
}

function contribPP(w, idxT, idxB, overallB) {
  if (overallB == null || overallB === 0 || idxT == null || idxB == null) return null;
  return (w * (idxT - idxB)) / overallB;
}

function destroy(key) {
  if (charts[key]) {
    charts[key].destroy();
    delete charts[key];
  }
}

function chartOpts(y) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#8fa3bf" } } },
    scales: {
      x: { ticks: { color: "#8fa3bf", font: { size: 10 }, maxRotation: 45 }, grid: { color: "rgba(42,59,85,.5)" } },
      y: { ticks: { color: "#8fa3bf" }, grid: { color: "rgba(42,59,85,.5)" }, title: { display: !!y, text: y || "", color: "#8fa3bf" } },
    },
  };
}

function shortName(s) {
  s = String(s || "").replace(/^\d+\.\s*/, "").trim();
  return s.length > 34 ? s.slice(0, 32) + "…" : s;
}

// Tabs
function switchTab(tabName) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  const btn = document.querySelector('.tab[data-tab="' + tabName + '"]');
  const panel = document.getElementById("panel-" + tabName);
  if (btn) btn.classList.add("active");
  if (panel) panel.classList.add("active");
  if (tabName === "prices") {
    try {
      if (typeof renderPriceEditor === "function") renderPriceEditor();
      if (typeof fillPriceTable === "function") fillPriceTable();
    } catch (e) {
      console.error(e);
      showStatus("Үнэ оруулах алдаа: " + e.message, "err");
    }
  }
  try {
    history.replaceState(null, "", "#" + tabName);
  } catch (_) {}
}

function openPricesTab() {
  // show content area if hidden
  const content = document.getElementById("content");
  if (content) content.style.display = "block";
  switchTab("prices");
  const panel = document.getElementById("panel-prices");
  if (panel) panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

function fillDefaults() {
  const p = normPeriod($("period").value);
  const d = defaultsFor(p);
  if (!d) {
    showStatus("Үндсэн сар: 2026-06 гэж бичнэ үү", "err");
    return;
  }
  _skip = true;
  $("period").value = p;
  $("vs1").value = d.v1;
  $("vs2").value = d.v2;
  $("vs3").value = d.v3;
  _skip = false;
  render();
}

function schedule() {
  if (_skip) return;
  clearTimeout(_timer);
  _timer = setTimeout(() => {
    const p = normPeriod($("period").value);
    if (/^\d{4}-\d{2}$/.test(p) && document.activeElement === $("period")) {
      const d = defaultsFor(p);
      if (d) {
        _skip = true;
        $("period").value = p;
        $("vs1").value = d.v1;
        $("vs2").value = d.v2;
        $("vs3").value = d.v3;
        _skip = false;
      }
    }
    ["period", "vs1", "vs2", "vs3"].forEach((id) => {
      if ($(id).value) $(id).value = normPeriod($(id).value);
    });
    render();
  }, 400);
}

function bindInputs() {
  ["period", "vs1", "vs2", "vs3"].forEach((id) => {
    $(id).addEventListener("input", schedule);
    $(id).addEventListener("change", schedule);
    $(id).addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        render();
      }
    });
  });
}

function getCtx() {
  const p = normPeriod($("period").value);
  let v1 = normPeriod($("vs1").value);
  let v2 = normPeriod($("vs2").value);
  let v3 = normPeriod($("vs3").value);
  const d = defaultsFor(p);
  if (d) {
    if (!v1) v1 = d.v1;
    if (!v2) v2 = d.v2;
    if (!v3) v3 = d.v3;
  }
  const t = monthIndex(p);
  if (t < 0) throw new Error("Үндсэн сар өгөгдөлд алга: " + p);
  const t1 = monthIndex(v1);
  const t2 = monthIndex(v2);
  const t3 = monthIndex(v3);
  return { p, v1, v2, v3, t, t1: t1 >= 0 ? t1 : null, t2: t2 >= 0 ? t2 : null, t3: t3 >= 0 ? t3 : null };
}

function render() {
  if (!DATA) return;
  try {
    const ctx = getCtx();
    _skip = true;
    $("period").value = ctx.p;
    $("vs1").value = ctx.v1;
    $("vs2").value = ctx.v2;
    $("vs3").value = ctx.v3;
    _skip = false;

    $("th1").textContent = "vs " + ctx.v1 + " %";
    $("th2").textContent = "vs " + ctx.v2 + " %";
    $("th3").textContent = "vs " + ctx.v3 + " %";
    $("cmpHint").textContent = "· " + ctx.p + " / " + ctx.v1 + " / " + ctx.v2 + " / " + ctx.v3;

    const nat = threeWay(DATA.national.overall, ctx.t, ctx.t1, ctx.t2, ctx.t3);
    const items = [
      { label: "Үндсэн сар", value: ctx.p, sub: "2023=100" },
      { label: "Улсын индекс", value: fmt(nat.index, 2), sub: "" },
      { label: "vs " + ctx.v1, value: (nat.c1 >= 0 ? "+" : "") + fmt(nat.c1, 1) + "%", cls: pctClass(nat.c1) },
      { label: "vs " + ctx.v2, value: (nat.c2 >= 0 ? "+" : "") + fmt(nat.c2, 1) + "%", cls: pctClass(nat.c2) },
      { label: "vs " + ctx.v3, value: (nat.c3 >= 0 ? "+" : "") + fmt(nat.c3, 1) + "%", cls: pctClass(nat.c3) },
    ];
    $("kpis").innerHTML = items
      .map(
        (k) => `<div class="kpi"><div class="label">${k.label}</div><div class="value ${k.cls || ""}">${k.value}</div><div class="sub">${k.sub || ""}</div></div>`
      )
      .join("");

    // Compare table
    const rows = [{ name: "Улс", ...nat }];
    Object.keys(DATA.aimags)
      .sort()
      .forEach((code) => {
        const a = DATA.aimags[code];
        const c = threeWay(a.overall, ctx.t, ctx.t1, ctx.t2, ctx.t3);
        rows.push({ name: a.name, weight: a.weight, ...c, code });
      });
    $("tblCompare").querySelector("tbody").innerHTML = rows
      .map(
        (r) =>
          `<tr><td>${r.name}</td><td>${fmt(r.index, 2)}</td>${pctCell(r.c1)}${pctCell(r.c2)}${pctCell(r.c3)}</tr>`
      )
      .join("");

    // Aimags
    const aim = Object.keys(DATA.aimags)
      .map((code) => {
        const a = DATA.aimags[code];
        const c = threeWay(a.overall, ctx.t, ctx.t1, ctx.t2, ctx.t3);
        return { code, name: a.name, weight: a.weight, ...c };
      })
      .sort((a, b) => (b.c1 || 0) - (a.c1 || 0));
    $("tblAimags").querySelector("tbody").innerHTML = aim
      .map(
        (a) =>
          `<tr><td>${a.code}</td><td>${a.name}</td><td>${fmt(a.weight, 3)}</td><td>${fmt(a.index, 2)}</td>${pctCell(a.c1)}${pctCell(a.c2)}${pctCell(a.c3)}</tr>`
      )
      .join("");

    // Groups national
    const gRows = Object.keys(DATA.national.groups)
      .sort((a, b) => +a - +b)
      .map((k) => {
        const g = DATA.national.groups[k];
        const c = threeWay(g.indices, ctx.t, ctx.t1, ctx.t2, ctx.t3);
        return { name: g.name, weight: g.weight, ...c };
      });
    $("tblGroups").querySelector("tbody").innerHTML = gRows
      .map(
        (g) =>
          `<tr><td>${g.name}</td><td>${fmt(g.weight, 2)}</td><td>${fmt(g.index, 2)}</td>${pctCell(g.c1)}${pctCell(g.c2)}${pctCell(g.c3)}</tr>`
      )
      .join("");

    // Special — зөвхөн Улс + УБ, Excel-ийн 1 тэмдэглэлтэй дэлгэрэнгүй бүлгүүд
    const sn = DATA.special.national || {};
    const su = DATA.special.ulaanbaatar || {};
    const keys = (DATA.special_order || Object.keys(sn)).filter((k) => sn[k]);
    $("tblSpecial").querySelector("tbody").innerHTML = keys
      .map((k) => {
        const n = sn[k];
        const u = su[k];
        const cn = threeWay(n.indices, ctx.t, ctx.t1, ctx.t2, ctx.t3);
        const cu = u ? threeWay(u.indices, ctx.t, ctx.t1, ctx.t2, ctx.t3) : {};
        const nItems = n.n_items != null ? n.n_items : "";
        return `<tr><td>${n.label}${nItems !== "" ? ` <span style="color:#8fa3bf;font-size:0.75rem">(${nItems})</span>` : ""}</td><td>${fmt(n.weight, 2)}</td><td>${fmt(cu.index, 2)}</td>${pctCell(cu.c1)}${pctCell(cu.c2)}${pctCell(cu.c3)}<td>${fmt(cn.index, 2)}</td>${pctCell(cn.c1)}${pctCell(cn.c2)}${pctCell(cn.c3)}</tr>`;
      })
      .join("");

    // Charts
    destroy("overall");
    destroy("yoy");
    destroy("aimags");
    const labels = DATA.months;
    const yoySeries = DATA.national.overall.map((v, i) =>
      i >= 12 ? pctChange(v, DATA.national.overall[i - 12]) : null
    );
    charts.overall = new Chart($("cOverall"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Улс",
            data: DATA.national.overall,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56,189,248,.12)",
            fill: true,
            tension: 0.25,
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "УБ",
            data: DATA.ulaanbaatar ? DATA.ulaanbaatar.overall : [],
            borderColor: "#a78bfa",
            tension: 0.25,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: chartOpts("индекс"),
    });
    charts.yoy = new Chart($("cYoy"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "YoY %",
            data: yoySeries,
            borderColor: "#f87171",
            tension: 0.25,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: chartOpts("%"),
    });
    charts.aimags = new Chart($("cAimags"), {
      type: "bar",
      data: {
        labels: aim.map((a) => a.name),
        datasets: [
          {
            label: "vs " + ctx.v1,
            data: aim.map((a) => a.c1),
            backgroundColor: aim.map((a) =>
              (a.c1 || 0) >= 0 ? "rgba(248,113,113,.7)" : "rgba(74,222,128,.7)"
            ),
            borderRadius: 4,
          },
        ],
      },
      options: { ...chartOpts("%"), indexAxis: "y", plugins: { legend: { display: false } } },
    });

    window.__ctx = ctx;
    renderContrib();
    renderRegions();
    $("content").style.display = "block";
    showStatus(
      "Сар: " + ctx.p + " · vs " + ctx.v1 + " / " + ctx.v2 + " / " + ctx.v3 +
        " · шинэчилсэн: " + (DATA.generated || ""),
      "ok"
    );
  } catch (e) {
    showStatus("Алдаа: " + e.message, "err");
  }
}

function renderContrib() {
  if (!DATA || !window.__ctx) return;
  const ctx = window.__ctx;
  const slot = $("contribSlot").value;
  const scope = $("contribScope").value;
  const tBase = slot === "1" ? ctx.t1 : slot === "2" ? ctx.t2 : ctx.t3;
  const baseLabel = slot === "1" ? ctx.v1 : slot === "2" ? ctx.v2 : ctx.v3;
  if (tBase == null) {
    $("contribHint").textContent = "Суурь сар өгөгдөлд алга";
    return;
  }

  const pack = scope === "ulaanbaatar" ? DATA.ulaanbaatar : DATA.national;
  if (!pack) {
    $("contribHint").textContent = "УБ өгөгдөл алга";
    return;
  }
  const overallB = pack.overall[tBase];
  const overallT = pack.overall[ctx.t];
  const inflAll = pctChange(overallT, overallB);
  const contAll = contribPP(100, overallT, overallB, overallB);

  $("contribHint").textContent =
    (scope === "national" ? "Улс" : "УБ") +
    ": " +
    ctx.p +
    " vs " +
    baseLabel +
    " · инфляц " +
    fmt(inflAll, 2) +
    "% · Cont = жин×(I_t−I_0)/I_ерөнхий_0";

  // COICOP groups
  const groups = Object.keys(pack.groups)
    .sort((a, b) => +a - +b)
    .map((k) => {
      const g = pack.groups[k];
      const idxT = g.indices[ctx.t];
      const idxB = g.indices[tBase];
      const cont = contribPP(g.weight, idxT, idxB, overallB);
      const infl = pctChange(idxT, idxB);
      return {
        name: g.name,
        weight: g.weight,
        index: idxT,
        inflation: infl,
        cont,
        share: contAll ? (cont / contAll) * 100 : null,
        overall: k === "8",
      };
    });

  // Special
  const sp = (DATA.special[scope] || DATA.special.national) || {};
  const special = [
    {
      name: "ЕРӨНХИЙ ИНДЕКС",
      weight: 100,
      index: overallT,
      inflation: inflAll,
      cont: contAll,
      share: 100,
      overall: true,
    },
  ];
  const spKeys = (DATA.special_order || Object.keys(sp)).filter((k) => sp[k]);
  spKeys.forEach((k) => {
    const g = sp[k];
    const idxT = g.indices[ctx.t];
    const idxB = g.indices[tBase];
    const cont = contribPP(g.weight, idxT, idxB, overallB);
    special.push({
      name: g.label,
      weight: g.weight,
      index: idxT,
      inflation: pctChange(idxT, idxB),
      cont,
      share: contAll ? (cont / contAll) * 100 : null,
      overall: false,
    });
  });

  const rowHtml = (r) =>
    `<tr style="${r.overall ? "font-weight:700" : ""}"><td>${r.name}</td><td>${fmt(r.weight, 2)}</td><td>${fmt(r.index, 2)}</td>${pctCell(r.inflation)}<td class="${pctClass(r.cont)}">${fmt(r.cont, 2)}</td><td>${fmt(r.share, 1)}</td></tr>`;

  $("tblContribG").querySelector("tbody").innerHTML = groups.map(rowHtml).join("");
  $("tblContribS").querySelector("tbody").innerHTML = special.map(rowHtml).join("");

  const gPlot = groups.filter((g) => !g.overall);
  const sPlot = special.filter((g) => !g.overall);
  destroy("cg");
  destroy("cs");
  charts.cg = new Chart($("cContribG"), {
    type: "bar",
    data: {
      labels: gPlot.map((g) => shortName(g.name)),
      datasets: [
        {
          data: gPlot.map((g) => g.cont),
          backgroundColor: gPlot.map((g) =>
            (g.cont || 0) >= 0 ? "rgba(248,113,113,.75)" : "rgba(74,222,128,.75)"
          ),
          borderRadius: 4,
        },
      ],
    },
    options: { ...chartOpts("нэгж"), indexAxis: "y", plugins: { legend: { display: false } } },
  });
  charts.cs = new Chart($("cContribS"), {
    type: "bar",
    data: {
      labels: sPlot.map((g) => g.name),
      datasets: [
        {
          data: sPlot.map((g) => g.cont),
          backgroundColor: sPlot.map((g) =>
            (g.cont || 0) >= 0 ? "rgba(129,140,248,.8)" : "rgba(74,222,128,.75)"
          ),
          borderRadius: 4,
        },
      ],
    },
    options: { ...chartOpts("нэгж"), indexAxis: "y", plugins: { legend: { display: false } } },
  });
}

function renderRegions() {
  if (!DATA || !window.__ctx) return;
  const ctx = window.__ctx;
  const scheme = $("regionScheme").value;
  const regs = DATA.regions[scheme] || {};
  const list = Object.keys(regs).map((name) => {
    const r = regs[name];
    const c = threeWay(r.overall, ctx.t, ctx.t1, ctx.t2, ctx.t3);
    return { name, codes: (r.codes || []).join(","), weight: r.weight, ...c };
  });
  $("tblRegions").querySelector("tbody").innerHTML = list
    .map(
      (r) =>
        `<tr><td>${r.name}</td><td>${r.codes}</td><td>${fmt(r.weight, 3)}</td><td>${fmt(r.index, 2)}</td>${pctCell(r.c1)}${pctCell(r.c2)}${pctCell(r.c3)}</tr>`
    )
    .join("");
  destroy("reg");
  charts.reg = new Chart($("cRegions"), {
    type: "bar",
    data: {
      labels: list.map((r) => r.name),
      datasets: [
        {
          label: "vs " + ctx.v1,
          data: list.map((r) => r.c1),
          backgroundColor: "rgba(56,189,248,.65)",
          borderRadius: 6,
        },
      ],
    },
    options: chartOpts("%"),
  });
}

async function init() {
  bindInputs();
  showStatus("Өгөгдөл ачаалж байна…", "info");
  try {
    const res = await fetch("data/cpi_bundle.json?v=4&t=" + Date.now());
    if (!res.ok) throw new Error("cpi_bundle.json олдсонгүй — web-export хийнэ үү");
    DATA = await res.json();
    if (!DATA.ub_edit || !DATA.ub_edit.products || !DATA.ub_edit.products.length) {
      console.warn("ub_edit missing in bundle");
    }
    const dl = $("periodList");
    DATA.months.forEach((p) => {
      const o = document.createElement("option");
      o.value = p;
      dl.appendChild(o);
    });
    // default last month
    const last = DATA.months[DATA.months.length - 1];
    // prefer last non-empty-ish: last month with overall != 100 or just last
    let def = last;
    for (let i = DATA.months.length - 1; i >= 0; i--) {
      if (Math.abs(DATA.national.overall[i] - 100) > 1e-6) {
        def = DATA.months[i];
        break;
      }
    }
    const d = defaultsFor(def);
    _skip = true;
    $("period").value = def;
    if (d) {
      $("vs1").value = d.v1;
      $("vs2").value = d.v2;
      $("vs3").value = d.v3;
    }
    _skip = false;
    $("footerMeta").textContent =
      "CPI 2023=100 · " + DATA.months.length + " сар · шинэчилсэн " + (DATA.generated || "");

    // Хэрэв УБ үнэ localStorage-д байвал автомат дахин тооцоо
    try {
      const ov = typeof ubLoadOverrides === "function" ? ubLoadOverrides() : {};
      if (DATA.ub_edit && Object.keys(ov).length && typeof recomputeUB === "function") {
        const rec = recomputeUB(DATA);
        applyUBToData(DATA, rec);
        showStatus("УБ-ын хадгалсан үнээр индекс шинэчлэгдлээ (local).", "ok");
      }
    } catch (e) {
      console.warn("UB recompute skip", e);
    }

    if (typeof renderPriceEditor === "function") renderPriceEditor();
    render();

    // #prices hash or first visit highlight
    const hash = (location.hash || "").replace("#", "");
    if (hash === "prices" || hash === "price") {
      openPricesTab();
    }
  } catch (e) {
    showStatus("Алдаа: " + e.message, "err");
  }
}

init();
