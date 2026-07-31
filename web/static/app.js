/* CPI dashboard — free period inputs + auto calculate */
let STATE = null;
let charts = {};
let AVAILABLE = [];
let DEFAULT_PERIOD = null;
let _debounceTimer = null;
let _skipAuto = false;

function $(id) { return document.getElementById(id); }

function showStatus(msg, type) {
  const el = $("status");
  el.className = "status show " + (type || "info");
  el.textContent = msg;
}

function hideStatus() {
  $("status").className = "status";
}

function setLoading(on) {
  $("loader").classList.toggle("show", on);
  $("btnLoad").disabled = on;
  $("btnPublish").disabled = on;
}

function fmt(n, d = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toFixed(d);
}

function pctClass(n) {
  if (n === null || n === undefined) return "";
  if (n > 0.05) return "pos";
  if (n < -0.05) return "neg";
  return "";
}

function pctCell(n) {
  const c = pctClass(n);
  const s = n === null || n === undefined ? "—" : (n > 0 ? "+" : "") + fmt(n, 1);
  return `<td class="${c}">${s}</td>`;
}

/** Normalize user typing to YYYY-MM if possible */
function normalizePeriodInput(s) {
  if (!s) return "";
  s = String(s).trim();
  let m = s.match(/^(\d{4})-(\d{1,2})$/);
  if (m) return m[1] + "-" + String(m[2]).padStart(2, "0");
  m = s.match(/^(\d{4})[./](\d{1,2})$/);
  if (m) return m[1] + "-" + String(m[2]).padStart(2, "0");
  m = s.match(/^(\d{4})(\d{2})$/);
  if (m) return m[1] + "-" + m[2];
  return s;
}

function getPeriods() {
  return {
    period: normalizePeriodInput($("period").value),
    vs_yoy: normalizePeriodInput($("vs_yoy").value),
    vs_ytd: normalizePeriodInput($("vs_ytd").value),
    vs_mom: normalizePeriodInput($("vs_mom").value),
  };
}

function queryString() {
  const p = getPeriods();
  const q = new URLSearchParams();
  if (p.period) q.set("period", p.period);
  if (p.vs_yoy) q.set("vs_yoy", p.vs_yoy);
  if (p.vs_ytd) q.set("vs_ytd", p.vs_ytd);
  if (p.vs_mom) q.set("vs_mom", p.vs_mom);
  return q.toString();
}

// Tabs
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("panel-" + btn.dataset.tab).classList.add("active");
  });
});

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.error || msg;
    } catch (_) {}
    throw new Error(msg);
  }
  return res;
}

/** Standard compare months for a main period YYYY-MM */
function computeDefaults(periodKey) {
  const m = periodKey.match(/^(\d{4})-(\d{2})$/);
  if (!m) return null;
  const y = +m[1], mo = +m[2];
  const prevMo = mo === 1 ? 12 : mo - 1;
  const prevY = mo === 1 ? y - 1 : y;
  return {
    yoy: `${y - 1}-${String(mo).padStart(2, "0")}`,
    ytd: `${y - 1}-12`,
    mom: `${prevY}-${String(prevMo).padStart(2, "0")}`,
  };
}

function fillDefaults() {
  const p = normalizePeriodInput($("period").value);
  if (!p) {
    showStatus("Эхлээд үндсэн сараа оруулна уу (ж.нь 2026-06)", "info");
    return;
  }
  const d = computeDefaults(p);
  if (!d) {
    showStatus("Үндсэн сар буруу форматтай. Жишээ: 2026-06", "err");
    return;
  }
  _skipAuto = true;
  $("period").value = p;
  $("vs_yoy").value = d.yoy;
  $("vs_ytd").value = d.ytd;
  $("vs_mom").value = d.mom;
  _skipAuto = false;
  loadDashboard();
}

function onPeriodMainChange() {
  const p = normalizePeriodInput($("period").value);
  if (!/^\d{4}-\d{2}$/.test(p)) return;
  // auto-fill compare boxes with standards when main period changes
  const d = computeDefaults(p);
  if (!d) return;
  _skipAuto = true;
  $("period").value = p;
  // only auto-fill if empty or previously looked like defaults
  $("vs_yoy").value = d.yoy;
  $("vs_ytd").value = d.ytd;
  $("vs_mom").value = d.mom;
  _skipAuto = false;
}

function scheduleAutoCalc(fromMain) {
  if (_skipAuto) return;
  clearTimeout(_debounceTimer);
  _debounceTimer = setTimeout(() => {
    if (fromMain) onPeriodMainChange();
    const p = normalizePeriodInput($("period").value);
    if (!p) return;
    // normalize displayed values
    _skipAuto = true;
    if ($("period").value) $("period").value = normalizePeriodInput($("period").value);
    if ($("vs_yoy").value) $("vs_yoy").value = normalizePeriodInput($("vs_yoy").value);
    if ($("vs_ytd").value) $("vs_ytd").value = normalizePeriodInput($("vs_ytd").value);
    if ($("vs_mom").value) $("vs_mom").value = normalizePeriodInput($("vs_mom").value);
    _skipAuto = false;
    loadDashboard();
  }, 450);
}

function bindAutoInputs() {
  const main = $("period");
  const others = [$("vs_yoy"), $("vs_ytd"), $("vs_mom")];

  main.addEventListener("change", () => scheduleAutoCalc(true));
  main.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onPeriodMainChange();
      loadDashboard();
    }
  });
  // typing: debounce auto
  main.addEventListener("input", () => scheduleAutoCalc(true));

  others.forEach((el) => {
    el.addEventListener("change", () => scheduleAutoCalc(false));
    el.addEventListener("input", () => scheduleAutoCalc(false));
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        loadDashboard();
      }
    });
  });
}

async function waitUntilReady(maxSec = 120) {
  for (let i = 0; i < maxSec; i++) {
    try {
      const res = await fetch("/api/status");
      const s = await res.json();
      if (s.load_error) {
        showStatus("Алдаа: " + s.load_error, "err");
        return false;
      }
      if (s.ready) return true;
      if (s.loading) {
        showStatus(
          "Excel тооцоолж байна… " + (i + 1) + " сек (ихэвчлэн 30–90 сек)",
          "info"
        );
        setLoading(true);
      } else if (!s.default_excel_exists) {
        showStatus(
          "Excel Desktop дээр алга: cpi calculation 2023=100.xlsx",
          "err"
        );
        return false;
      } else {
        showStatus(
          "Өгөгдөл бэлэн биш. «Excel дахин» дарна уу… (" + (i + 1) + "с)",
          "info"
        );
      }
    } catch (e) {
      showStatus("Серверт холбогдохгүй байна… " + (i + 1) + "с", "info");
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  showStatus("Хэт удаан. «Excel дахин» товчийг дарна уу.", "err");
  return false;
}

async function loadPeriods() {
  const res = await api("/api/periods");
  const data = await res.json();
  AVAILABLE = data.periods || [];
  DEFAULT_PERIOD = data.default;
  const dl = $("periodList");
  dl.innerHTML = "";
  AVAILABLE.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    dl.appendChild(opt);
  });
  if (!data.ready) {
    showStatus("Өгөгдөл бэлдэж байна… эсвэл «Excel дахин» дарна уу.", "info");
    return;
  }
  if (!$("period").value && DEFAULT_PERIOD) {
    _skipAuto = true;
    $("period").value = DEFAULT_PERIOD;
    const d = computeDefaults(DEFAULT_PERIOD);
    if (d) {
      $("vs_yoy").value = d.yoy;
      $("vs_ytd").value = d.ytd;
      $("vs_mom").value = d.mom;
    }
    _skipAuto = false;
  }
}

async function recalculate() {
  setLoading(true);
  showStatus("Excel уншиж, бүх индекс тооцоолж байна… Хүлээнэ үү.", "info");
  try {
    const res = await api("/api/calculate", { method: "POST" });
    const data = await res.json();
    showStatus(
      "Тооцоолол амжилттай (" + fmt(data.seconds, 1) + " сек). " +
        data.months + " сар, " + data.aimags + " аймаг.",
      "ok"
    );
    await loadPeriods();
    await loadDashboard();
  } catch (e) {
    showStatus("Алдаа: " + e.message, "err");
  } finally {
    setLoading(false);
  }
}

async function loadDashboard() {
  const p = getPeriods();
  if (!p.period) {
    showStatus("Үндсэн сараа оруулна уу. Жишээ: 2026-06", "info");
    return;
  }
  setLoading(true);
  hideStatus();
  try {
    const res = await api("/api/dashboard?" + queryString());
    STATE = await res.json();
    $("content").style.display = "block";
    // sync inputs to resolved values
    _skipAuto = true;
    $("period").value = STATE.period;
    if (STATE.compare) {
      $("vs_yoy").value = STATE.compare.yoy;
      $("vs_ytd").value = STATE.compare.ytd;
      $("vs_mom").value = STATE.compare.mom;
    }
    _skipAuto = false;
    renderAll();
    const c = STATE.compare;
    showStatus(
      STATE.period_label +
        "  ·  vs " + c.yoy + " / " + c.ytd + " / " + c.mom,
      "ok"
    );
  } catch (e) {
    showStatus("Алдаа: " + e.message, "err");
  } finally {
    setLoading(false);
  }
}

async function publishTables() {
  const p = getPeriods();
  if (!p.period) {
    showStatus("Үндсэн сараа оруулна уу.", "err");
    return;
  }
  setLoading(true);
  showStatus("Table 1–11 үүсгэж байна…", "info");
  try {
    const res = await api(
      "/api/publish?period=" + encodeURIComponent(p.period),
      { method: "POST" }
    );
    const data = await res.json();
    showStatus("Бэлэн: " + data.filename, "ok");
    window.location.href =
      "/api/download/publication?period=" + encodeURIComponent(p.period);
  } catch (e) {
    showStatus("Алдаа: " + e.message, "err");
  } finally {
    setLoading(false);
  }
}

function destroyChart(key) {
  if (charts[key]) {
    charts[key].destroy();
    delete charts[key];
  }
}

function renderAll() {
  renderKpis();
  renderCompare();
  renderAimags();
  renderGroups();
  renderSpecial();
  renderContribution();
  renderRegions();
  renderCharts();
  $("dlComp").href =
    "/api/download/comparison?period=" + encodeURIComponent(STATE.period);
  $("dlHint").textContent =
    "Сар: " + STATE.period +
    " · харьцуулалт: " +
    STATE.compare.yoy + ", " + STATE.compare.ytd + ", " + STATE.compare.mom;
}

function renderContribution() {
  if (!STATE || !STATE.contribution) return;
  const slot = $("contribSlot") ? $("contribSlot").value : "yoy";
  const scope = $("contribScope") ? $("contribScope").value : "national";
  const block = STATE.contribution[slot];
  if (!block) {
    if ($("contribHint")) {
      $("contribHint").textContent = "Энэ харьцуулалтын суурь сар өгөгдөлд алга.";
    }
    return;
  }
  const data = block[scope] || {};
  const groups = data.groups || [];
  const special = data.special || [];
  const base = block.base_period || STATE.compare[slot];
  const cur = STATE.period;

  // update slot option labels with actual months
  if ($("contribSlot")) {
    const opt0 = $("contribSlot").options[0];
    const opt1 = $("contribSlot").options[1];
    const opt2 = $("contribSlot").options[2];
    if (opt0) opt0.textContent = "1: vs " + STATE.compare.yoy;
    if (opt1) opt1.textContent = "2: vs " + STATE.compare.ytd;
    if (opt2) opt2.textContent = "3: vs " + STATE.compare.mom;
  }

  if ($("contribBaseLabel")) {
    $("contribBaseLabel").textContent = "· " + cur + " vs " + base;
  }
  if ($("contribHint")) {
    const overall = groups.find((g) => g.is_overall);
    const inf = overall ? fmt(overall.inflation, 2) : "—";
    $("contribHint").textContent =
      (scope === "national" ? "Улс" : "Улаанбаатар") +
      ": " + cur + " / " + base +
      " · инфляц " + inf + "%" +
      " · Cont = жин × (I_t − I_0) / I_ерөнхий_0 · Share = Cont / инфляц × 100";
  }

  function rowHtml(r) {
    const bold = r.is_overall ? "font-weight:700" : "";
    return `
      <tr style="${bold}">
        <td>${r.name || r.key || ""}</td>
        <td>${fmt(r.weight, 2)}</td>
        <td>${fmt(r.index, 2)}</td>
        ${pctCell(r.inflation)}
        <td class="${pctClass(r.contrib_pp)}">${r.contrib_pp == null ? "—" : fmt(r.contrib_pp, 2)}</td>
        <td>${r.contrib_share == null ? "—" : fmt(r.contrib_share, 1)}</td>
      </tr>`;
  }

  if ($("tblContribGroups")) {
    $("tblContribGroups").querySelector("tbody").innerHTML = groups.map(rowHtml).join("");
  }
  if ($("tblContribSpecial")) {
    $("tblContribSpecial").querySelector("tbody").innerHTML = special.map(rowHtml).join("");
  }

  // charts: exclude overall, sort by abs contrib
  const gPlot = groups.filter((g) => !g.is_overall);
  const sPlot = special.filter((g) => !g.is_overall);

  destroyChart("contribG");
  destroyChart("contribS");

  if ($("chartContribGroups")) {
    charts.contribG = new Chart($("chartContribGroups"), {
      type: "bar",
      data: {
        labels: gPlot.map((g) => shortName(g.name)),
        datasets: [
          {
            label: "Оролцоо (нэгж)",
            data: gPlot.map((g) => g.contrib_pp),
            backgroundColor: gPlot.map((g) =>
              (g.contrib_pp || 0) >= 0
                ? "rgba(248,113,113,0.75)"
                : "rgba(74,222,128,0.75)"
            ),
            borderRadius: 4,
          },
        ],
      },
      options: {
        ...chartOpts("нэгж"),
        indexAxis: "y",
        plugins: { legend: { display: false } },
      },
    });
  }

  if ($("chartContribSpecial")) {
    charts.contribS = new Chart($("chartContribSpecial"), {
      type: "bar",
      data: {
        labels: sPlot.map((g) => g.name),
        datasets: [
          {
            label: "Оролцоо (нэгж)",
            data: sPlot.map((g) => g.contrib_pp),
            backgroundColor: sPlot.map((g) =>
              (g.contrib_pp || 0) >= 0
                ? "rgba(129,140,248,0.8)"
                : "rgba(74,222,128,0.75)"
            ),
            borderRadius: 4,
          },
        ],
      },
      options: {
        ...chartOpts("нэгж"),
        indexAxis: "y",
        plugins: { legend: { display: false } },
      },
    });
  }
}

function shortName(s) {
  if (!s) return "";
  s = String(s);
  // drop leading codes like "01.   "
  s = s.replace(/^\d+\.\s*/, "").trim();
  if (s.length > 36) return s.slice(0, 34) + "…";
  return s;
}

function renderKpis() {
  const n = STATE.national;
  const c = STATE.compare;
  const items = [
    { label: "Үндсэн сар", value: STATE.period, sub: STATE.period_label },
    { label: "Индекс", value: fmt(n.index, 2), sub: "2023=100" },
    {
      label: "vs " + c.yoy,
      value: (n.yoy >= 0 ? "+" : "") + fmt(n.yoy, 1) + "%",
      sub: "харьцуулалт 1",
      cls: pctClass(n.yoy),
    },
    {
      label: "vs " + c.ytd,
      value: (n.ytd >= 0 ? "+" : "") + fmt(n.ytd, 1) + "%",
      sub: "харьцуулалт 2",
      cls: pctClass(n.ytd),
    },
    {
      label: "vs " + c.mom,
      value: (n.mom >= 0 ? "+" : "") + fmt(n.mom, 1) + "%",
      sub: "харьцуулалт 3",
      cls: pctClass(n.mom),
    },
  ];
  $("kpis").innerHTML = items
    .map(
      (k) => `
    <div class="kpi">
      <div class="label">${k.label}</div>
      <div class="value ${k.cls || ""}">${k.value}</div>
      <div class="sub">${k.sub || ""}</div>
    </div>
  `
    )
    .join("");
  $("chartPeriod").textContent = STATE.period;
  $("cmpHint").textContent =
    "· " + STATE.period + " / " + c.yoy + " / " + c.ytd + " / " + c.mom;
  $("thYoy").textContent = "vs " + c.yoy + " %";
  $("thYtd").textContent = "vs " + c.ytd + " %";
  $("thMom").textContent = "vs " + c.mom + " %";
}

function renderCompare() {
  const rows = [
    { name: "Улс", ...STATE.national },
    ...STATE.aimags.map((a) => ({ name: a.name, ...a })),
  ];
  $("tblCompare").querySelector("tbody").innerHTML = rows
    .map(
      (r) => `
    <tr>
      <td>${r.name}</td>
      <td>${fmt(r.index, 2)}</td>
      ${pctCell(r.yoy)}
      ${pctCell(r.ytd)}
      ${pctCell(r.mom)}
    </tr>
  `
    )
    .join("");
}

function renderAimags() {
  const sorted = [...STATE.aimags].sort((a, b) => (b.yoy || 0) - (a.yoy || 0));
  $("tblAimags").querySelector("tbody").innerHTML = sorted
    .map(
      (a) => `
    <tr>
      <td>${a.code}</td>
      <td>${a.name}</td>
      <td>${fmt(a.weight, 3)}</td>
      <td>${fmt(a.index, 2)}</td>
      ${pctCell(a.yoy)}
      ${pctCell(a.ytd)}
      ${pctCell(a.mom)}
    </tr>
  `
    )
    .join("");
}

function renderGroups() {
  $("tblGroups").querySelector("tbody").innerHTML = STATE.groups
    .map(
      (g) => `
    <tr>
      <td>${g.name}</td>
      <td>${fmt(g.weight, 3)}</td>
      <td>${fmt(g.index, 2)}</td>
      ${pctCell(g.yoy)}
      ${pctCell(g.ytd)}
      ${pctCell(g.mom)}
    </tr>
  `
    )
    .join("");
}

function renderSpecial() {
  $("tblSpecial").querySelector("tbody").innerHTML = STATE.special
    .map(
      (g) => `
    <tr>
      <td>${g.label}</td>
      <td>${fmt(g.ub_index, 2)}</td>
      ${pctCell(g.ub_yoy)}
      <td>${fmt(g.nat_index, 2)}</td>
      ${pctCell(g.nat_yoy)}
    </tr>
  `
    )
    .join("");
}

function renderRegions() {
  const scheme = $("regionScheme").value;
  const list = STATE.regions[scheme] || [];
  $("tblRegions").querySelector("tbody").innerHTML = list
    .map(
      (r) => `
    <tr>
      <td>${r.name}</td>
      <td>${r.codes}</td>
      <td>${fmt(r.weight, 3)}</td>
      <td>${fmt(r.index, 2)}</td>
      ${pctCell(r.yoy)}
      ${pctCell(r.ytd)}
      ${pctCell(r.mom)}
    </tr>
  `
    )
    .join("");

  destroyChart("regions");
  charts.regions = new Chart($("chartRegions"), {
    type: "bar",
    data: {
      labels: list.map((r) => r.name),
      datasets: [
        {
          label: "vs " + STATE.compare.yoy + " %",
          data: list.map((r) => r.yoy),
          backgroundColor: "rgba(56,189,248,0.65)",
          borderRadius: 6,
        },
      ],
    },
    options: chartOpts("%"),
  });
}

function chartOpts(yTitle) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: "#8fa3bf" } },
    },
    scales: {
      x: {
        ticks: {
          color: "#8fa3bf",
          maxRotation: 45,
          minRotation: 0,
          font: { size: 10 },
        },
        grid: { color: "rgba(42,59,85,0.5)" },
      },
      y: {
        ticks: { color: "#8fa3bf" },
        grid: { color: "rgba(42,59,85,0.5)" },
        title: {
          display: !!yTitle,
          text: yTitle || "",
          color: "#8fa3bf",
        },
      },
    },
  };
}

function renderCharts() {
  const labels = STATE.series.months;
  destroyChart("overall");
  destroyChart("yoy");
  destroyChart("aimags");

  charts.overall = new Chart($("chartOverall"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Улс",
          data: STATE.series.national,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56,189,248,0.12)",
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: "Улаанбаатар",
          data: STATE.series.ub,
          borderColor: "#a78bfa",
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: chartOpts("индекс"),
  });

  charts.yoy = new Chart($("chartYoy"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Улс 12 сарын %",
          data: STATE.series.national_yoy,
          borderColor: "#f87171",
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: chartOpts("%"),
  });

  const sorted = [...STATE.aimags].sort((a, b) => (b.yoy || 0) - (a.yoy || 0));
  charts.aimags = new Chart($("chartAimags"), {
    type: "bar",
    data: {
      labels: sorted.map((a) => a.name),
      datasets: [
        {
          label: "vs " + STATE.compare.yoy + " %",
          data: sorted.map((a) => a.yoy),
          backgroundColor: sorted.map((a) =>
            (a.yoy || 0) >= 0
              ? "rgba(248,113,113,0.7)"
              : "rgba(74,222,128,0.7)"
          ),
          borderRadius: 4,
        },
      ],
    },
    options: {
      ...chartOpts("%"),
      indexAxis: "y",
      plugins: { legend: { display: false } },
    },
  });
}

// init
(async function init() {
  bindAutoInputs();
  try {
    const ready = await waitUntilReady(120);
    setLoading(false);
    if (!ready) {
      showStatus(
        "Бэлэн болоогүй. Дээрх «Excel дахин» товчийг дарж тооцоолно уу.",
        "info"
      );
      return;
    }
    await loadPeriods();
    await loadDashboard();
  } catch (e) {
    setLoading(false);
    showStatus(
      "Эхлүүлэхэд: " + e.message + " — «Excel дахин» дарна уу.",
      "info"
    );
  }
})();
