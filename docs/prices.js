/**
 * Улаанбаатар — барааны үнэ ХАРАХ (оруулах биш)
 * Үндсэн сар + Харьцуулах 1/2/3 = 3 түвшин
 */
let _selectedProductRow = null;

function ubProducts() {
  if (!DATA || !DATA.ub_edit || !DATA.ub_edit.products) return [];
  return DATA.ub_edit.products;
}

function priceAt(product, periodKey) {
  if (!product || !DATA) return null;
  const i = DATA.months.indexOf(periodKey);
  if (i < 0) return null;
  const p = product.prices[i];
  if (p == null || p === 0) return null;
  return p;
}

function pricePct(cur, base) {
  if (cur == null || base == null || base === 0) return null;
  return (cur / base) * 100 - 100;
}

function getCompareCtx() {
  // reuse main period fields
  const p = typeof normPeriod === "function" ? normPeriod($("period").value) : $("period").value;
  let v1 = typeof normPeriod === "function" ? normPeriod($("vs1").value) : $("vs1").value;
  let v2 = typeof normPeriod === "function" ? normPeriod($("vs2").value) : $("vs2").value;
  let v3 = typeof normPeriod === "function" ? normPeriod($("vs3").value) : $("vs3").value;
  const d = typeof defaultsFor === "function" ? defaultsFor(p) : null;
  if (d) {
    if (!v1) v1 = d.v1;
    if (!v2) v2 = d.v2;
    if (!v3) v3 = d.v3;
  }
  return { p, v1, v2, v3 };
}

function renderPriceEditor() {
  if (!DATA || !DATA.ub_edit) {
    const st = document.getElementById("priceStatus");
    if (st) st.textContent = "Үнийн өгөгдөл алга (ub_edit).";
    return;
  }
  // fill datalist
  const dl = document.getElementById("productList");
  if (dl && !dl.options.length) {
    ubProducts().forEach((pr) => {
      if ((pr.weight || 0) <= 0 && !(pr.prices || []).some((x) => x)) return;
      const o = document.createElement("option");
      o.value = pr.name;
      o.label = (pr.item_no != null ? pr.item_no + ". " : "") + pr.name;
      dl.appendChild(o);
    });
  }
  fillPriceView();
}

function fillPriceView() {
  if (!DATA || !DATA.ub_edit) return;
  const ctx = getCompareCtx();
  const q = (document.getElementById("priceSearch").value || "").trim().toLowerCase();
  const onlyW = document.getElementById("priceOnlyWeight");
  let list = ubProducts();

  if (onlyW && onlyW.checked) {
    list = list.filter(
      (p) =>
        (p.weight || 0) > 0 ||
        (p.prices || []).some((x) => x != null && x !== 0)
    );
  }
  if (q) {
    list = list.filter(
      (p) =>
        (p.name || "").toLowerCase().includes(q) ||
        String(p.item_no || "").includes(q) ||
        String(p.row).includes(q)
    );
  }

  // headers
  const setH = (id, label) => {
    const el = document.getElementById(id);
    if (el) el.textContent = label;
  };
  setH("thP0", ctx.p || "Үндсэн");
  setH("thP1", ctx.v1 || "vs1");
  setH("thP2", ctx.v2 || "vs2");
  setH("thP3", ctx.v3 || "vs3");

  const tbody = document.querySelector("#tblPrices tbody");
  if (!tbody) return;

  tbody.innerHTML = list
    .map((pr) => {
      const p0 = priceAt(pr, ctx.p);
      const p1 = priceAt(pr, ctx.v1);
      const p2 = priceAt(pr, ctx.v2);
      const p3 = priceAt(pr, ctx.v3);
      const c1 = pricePct(p0, p1);
      const c2 = pricePct(p0, p2);
      const c3 = pricePct(p0, p3);
      const sel = _selectedProductRow === pr.row ? "price-selected" : "";
      return `<tr class="${sel}" data-row="${pr.row}" onclick="selectProduct(${pr.row})" style="cursor:pointer">
        <td>${pr.item_no != null ? pr.item_no : ""}</td>
        <td class="price-name">${escapeHtml(pr.name)}</td>
        <td>${fmt(pr.weight, 4)}</td>
        <td>${p0 == null ? "—" : fmt(p0, 1)}</td>
        <td>${p1 == null ? "—" : fmt(p1, 1)}</td>
        <td>${p2 == null ? "—" : fmt(p2, 1)}</td>
        <td>${p3 == null ? "—" : fmt(p3, 1)}</td>
        ${typeof pctCell === "function" ? pctCell(c1) : "<td>—</td>"}
        ${typeof pctCell === "function" ? pctCell(c2) : "<td>—</td>"}
        ${typeof pctCell === "function" ? pctCell(c3) : "<td>—</td>"}
      </tr>`;
    })
    .join("");

  const st = document.getElementById("priceStatus");
  if (st) {
    st.textContent =
      "УБ · " +
      list.length +
      " бараа · үндсэн " +
      (ctx.p || "—") +
      " · vs " +
      (ctx.v1 || "—") +
      " / " +
      (ctx.v2 || "—") +
      " / " +
      (ctx.v3 || "—");
  }

  if (_selectedProductRow != null) {
    showProductDetail(_selectedProductRow);
  }
}

function onProductSearch() {
  const q = (document.getElementById("priceSearch").value || "").trim();
  // if exact match name, select it
  const hit = ubProducts().find((p) => p.name === q);
  if (hit) {
    selectProduct(hit.row);
  } else {
    fillPriceView();
  }
}

function selectProduct(row) {
  _selectedProductRow = row;
  showProductDetail(row);
  fillPriceView();
}

function showProductDetail(row) {
  const pr = ubProducts().find((p) => p.row === row);
  const box = document.getElementById("productDetail");
  if (!pr || !box) return;
  box.style.display = "block";
  const ctx = getCompareCtx();
  document.getElementById("productDetailName").textContent =
    (pr.item_no != null ? pr.item_no + ". " : "") + pr.name;

  const p0 = priceAt(pr, ctx.p);
  const p1 = priceAt(pr, ctx.v1);
  const p2 = priceAt(pr, ctx.v2);
  const p3 = priceAt(pr, ctx.v3);
  const c1 = pricePct(p0, p1);
  const c2 = pricePct(p0, p2);
  const c3 = pricePct(p0, p3);

  document.getElementById("productPriceKpis").innerHTML = [
    { label: "Үндсэн · " + ctx.p, value: p0 == null ? "—" : fmt(p0, 1) + " ₮", sub: "одоогийн" },
    {
      label: "vs " + ctx.v1,
      value: c1 == null ? "—" : (c1 >= 0 ? "+" : "") + fmt(c1, 1) + "%",
      sub: p1 == null ? "—" : fmt(p1, 1) + " ₮",
      cls: typeof pctClass === "function" ? pctClass(c1) : "",
    },
    {
      label: "vs " + ctx.v2,
      value: c2 == null ? "—" : (c2 >= 0 ? "+" : "") + fmt(c2, 1) + "%",
      sub: p2 == null ? "—" : fmt(p2, 1) + " ₮",
      cls: typeof pctClass === "function" ? pctClass(c2) : "",
    },
    {
      label: "vs " + ctx.v3,
      value: c3 == null ? "—" : (c3 >= 0 ? "+" : "") + fmt(c3, 1) + "%",
      sub: p3 == null ? "—" : fmt(p3, 1) + " ₮",
      cls: typeof pctClass === "function" ? pctClass(c3) : "",
    },
  ]
    .map(
      (k) =>
        `<div class="kpi"><div class="label">${k.label}</div><div class="value ${k.cls || ""}">${k.value}</div><div class="sub">${k.sub || ""}</div></div>`
    )
    .join("");

  const levels = [
    { name: "Үндсэн сар", period: ctx.p, price: p0, pct: null },
    { name: "Харьцуулалт 1", period: ctx.v1, price: p1, pct: c1 },
    { name: "Харьцуулалт 2", period: ctx.v2, price: p2, pct: c2 },
    { name: "Харьцуулалт 3", period: ctx.v3, price: p3, pct: c3 },
  ];
  document.querySelector("#tblProductCompare tbody").innerHTML = levels
    .map((L) => {
      const pctTd =
        L.pct == null
          ? "<td>—</td>"
          : typeof pctCell === "function"
            ? pctCell(L.pct)
            : `<td>${fmt(L.pct, 1)}</td>`;
      return `<tr>
        <td>${L.name}</td>
        <td>${L.period || "—"}</td>
        <td>${L.price == null ? "—" : fmt(L.price, 1)}</td>
        ${pctTd}
      </tr>`;
    })
    .join("");

  // history chart
  if (typeof Chart !== "undefined" && pr.prices) {
    if (window._productChart) {
      window._productChart.destroy();
      window._productChart = null;
    }
    const labels = DATA.months;
    const vals = pr.prices.map((x) => (x == null || x === 0 ? null : x));
    window._productChart = new Chart(document.getElementById("cProductPrice"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Үнэ ₮",
            data: vals,
            borderColor: "#fbbf24",
            backgroundColor: "rgba(251,191,36,.12)",
            fill: true,
            tension: 0.25,
            pointRadius: 0,
            borderWidth: 2,
            spanGaps: false,
          },
        ],
      },
      options:
        typeof chartOpts === "function"
          ? chartOpts("₮")
          : { responsive: true, maintainAspectRatio: false },
    });
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// keep name used by app.js
function fillPriceTable() {
  fillPriceView();
}
