/* CPI dashboard frontend */
let STATE = null;
let charts = {};

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

async function loadPeriods() {
  const res = await api("/api/periods");
  const data = await res.json();
  const sel = $("period");
  sel.innerHTML = "";
  (data.periods || []).forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    if (p === data.default) opt.selected = true;
    sel.appendChild(opt);
  });
  if (!data.ready) {
    showStatus("Эхлээд тооцоолол хийнэ. «Дахин тооцоолох» дарна уу (30–90 сек).", "info");
  }
}

async function recalculate() {
  setLoading(true);
  showStatus("Excel уншиж, бүх индекс тооцоолж байна… Хүлээнэ үү.", "info");
  try {
    const res = await api("/api/calculate", { method: "POST" });
    const data = await res.json();
    showStatus("Тооцоолол амжилттай (" + fmt(data.seconds, 1) + " сек). " + data.months + " сар, " + data.aimags + " аймаг.", "ok");
    await loadPeriods();
    await loadDashboard();
  } catch (e) {
    showStatus("Алдаа: " + e.message, "err");
  } finally {
    setLoading(false);
  }
}

async function loadDashboard() {
  const period = $("period").value;
  if (!period) {
    showStatus("Хугацаа сонгоно уу. Эсвэл «Дахин тооцоолох» дарна уу.", "info");
    return;
  }
  setLoading(true);
  hideStatus();
  try {
    const res = await api("/api/dashboard?period=" + encodeURIComponent(period));
    STATE = await res.json();
    $("content").style.display = "block";
    renderAll();
    showStatus("Хугацаа: " + STATE.period_label + " · " + STATE.period_en, "ok");
  } catch (e) {
    showStatus("Алдаа: " + e.message + " — эхлээд «Дахин тооцоолох» туршина уу.", "err");
    $("content").style.display = "none";
  } finally {
    setLoading(false);
  }
}

async function publishTables() {
  const period = $("period").value;
  if (!period) {
    showStatus("Хугацаа сонгоно уу.", "err");
    return;
  }
  setLoading(true);
  showStatus("Table 1–11 үүсгэж байна…", "info");
  try {
    const res = await api("/api/publish?period=" + encodeURIComponent(period), { method: "POST" });
    const data = await res.json();
    showStatus("Бэлэн: " + data.filename, "ok");
    // download
    window.location.href = "/api/download/publication?period=" + encodeURIComponent(period);
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
  renderRegions();
  renderCharts();
  $("dlComp").href = "/api/download/comparison?period=" + encodeURIComponent(STATE.period);
  $("dlHint").textContent = "Сонгосон сар: " + STATE.period;
}

function renderKpis() {
  const n = STATE.national;
  const items = [
    { label: "Сар", value: STATE.period, sub: STATE.period_label },
    { label: "Улсын индекс", value: fmt(n.index, 2), sub: "2023=100" },
    { label: "Өмнөх оны мөн үе", value: (n.yoy >= 0 ? "+" : "") + fmt(n.yoy, 1) + "%", sub: "YoY", cls: pctClass(n.yoy) },
    { label: "Өмнөх оны эцэс", value: (n.ytd >= 0 ? "+" : "") + fmt(n.ytd, 1) + "%", sub: "vs XII", cls: pctClass(n.ytd) },
    { label: "Өмнөх сар", value: (n.mom >= 0 ? "+" : "") + fmt(n.mom, 1) + "%", sub: "MoM", cls: pctClass(n.mom) },
  ];
  $("kpis").innerHTML = items.map((k) => `
    <div class="kpi">
      <div class="label">${k.label}</div>
      <div class="value ${k.cls || ""}">${k.value}</div>
      <div class="sub">${k.sub || ""}</div>
    </div>
  `).join("");
  $("chartPeriod").textContent = STATE.period;
}

function renderCompare() {
  const rows = [
    { name: "Улс", ...STATE.national },
    ...STATE.aimags.map((a) => ({ name: a.name, ...a })),
  ];
  $("tblCompare").querySelector("tbody").innerHTML = rows.map((r) => `
    <tr>
      <td>${r.name}</td>
      <td>${fmt(r.index, 2)}</td>
      ${pctCell(r.yoy)}
      ${pctCell(r.ytd)}
      ${pctCell(r.mom)}
    </tr>
  `).join("");
}

function renderAimags() {
  const sorted = [...STATE.aimags].sort((a, b) => b.index - a.index);
  $("tblAimags").querySelector("tbody").innerHTML = sorted.map((a) => `
    <tr>
      <td>${a.code}</td>
      <td>${a.name}</td>
      <td>${fmt(a.weight, 3)}</td>
      <td>${fmt(a.index, 2)}</td>
      ${pctCell(a.yoy)}
      ${pctCell(a.ytd)}
      ${pctCell(a.mom)}
    </tr>
  `).join("");
}

function renderGroups() {
  $("tblGroups").querySelector("tbody").innerHTML = STATE.groups.map((g) => `
    <tr>
      <td>${g.name}</td>
      <td>${fmt(g.weight, 3)}</td>
      <td>${fmt(g.index, 2)}</td>
      ${pctCell(g.yoy)}
      ${pctCell(g.ytd)}
      ${pctCell(g.mom)}
    </tr>
  `).join("");
}

function renderSpecial() {
  $("tblSpecial").querySelector("tbody").innerHTML = STATE.special.map((g) => `
    <tr>
      <td>${g.label}</td>
      <td>${fmt(g.ub_index, 2)}</td>
      ${pctCell(g.ub_yoy)}
      <td>${fmt(g.nat_index, 2)}</td>
      ${pctCell(g.nat_yoy)}
    </tr>
  `).join("");
}

function renderRegions() {
  const scheme = $("regionScheme").value;
  const list = STATE.regions[scheme] || [];
  $("tblRegions").querySelector("tbody").innerHTML = list.map((r) => `
    <tr>
      <td>${r.name}</td>
      <td>${r.codes}</td>
      <td>${fmt(r.weight, 3)}</td>
      <td>${fmt(r.index, 2)}</td>
      ${pctCell(r.yoy)}
      ${pctCell(r.ytd)}
      ${pctCell(r.mom)}
    </tr>
  `).join("");

  destroyChart("regions");
  const ctx = $("chartRegions");
  charts.regions = new Chart(ctx, {
    type: "bar",
    data: {
      labels: list.map((r) => r.name),
      datasets: [
        {
          label: "YoY %",
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
        ticks: { color: "#8fa3bf", maxRotation: 45, minRotation: 0, font: { size: 10 } },
        grid: { color: "rgba(42,59,85,0.5)" },
      },
      y: {
        ticks: { color: "#8fa3bf" },
        grid: { color: "rgba(42,59,85,0.5)" },
        title: { display: !!yTitle, text: yTitle || "", color: "#8fa3bf" },
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
          label: "Улс YoY %",
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

  const sorted = [...STATE.aimags].sort((a, b) => b.yoy - a.yoy);
  charts.aimags = new Chart($("chartAimags"), {
    type: "bar",
    data: {
      labels: sorted.map((a) => a.name),
      datasets: [
        {
          label: "YoY %",
          data: sorted.map((a) => a.yoy),
          backgroundColor: sorted.map((a) =>
            a.yoy >= 0 ? "rgba(248,113,113,0.7)" : "rgba(74,222,128,0.7)"
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
  try {
    await loadPeriods();
    // try load dashboard if cache exists
    await loadDashboard();
  } catch (e) {
    showStatus("Эхлүүлэхэд: " + e.message + " — «Дахин тооцоолох» дарна уу.", "info");
  }
})();
