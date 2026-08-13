/**
 * Улаанбаатарын үнэ оруулах + индекс дахин тооцох (client-side)
 * GitHub Pages — backend шаардлагагүй. localStorage-д хадгална.
 */
const UB_STORE_KEY = "cpi_ub_prices_v1";

function ubLoadOverrides() {
  try {
    return JSON.parse(localStorage.getItem(UB_STORE_KEY) || "{}");
  } catch {
    return {};
  }
}

function ubSaveOverrides(obj) {
  localStorage.setItem(UB_STORE_KEY, JSON.stringify(obj));
}

function ubClearOverrides() {
  localStorage.removeItem(UB_STORE_KEY);
}

/** Merge overrides into product prices: overrides[row][period] = price */
function ubMergedProducts(data) {
  if (!data.ub_edit) return [];
  const ov = ubLoadOverrides();
  return data.ub_edit.products.map((p) => {
    const prices = p.prices.slice();
    const rowOv = ov[String(p.row)] || {};
    data.months.forEach((m, i) => {
      if (rowOv[m] != null && rowOv[m] !== "") {
        const n = Number(rowOv[m]);
        prices[i] = Number.isFinite(n) ? n : prices[i];
      }
    });
    return { ...p, prices };
  });
}

function basePrice(prices, baseN) {
  const vals = prices.slice(0, baseN).filter((p) => p != null && p !== 0);
  if (!vals.length) {
    const any = prices.filter((p) => p != null && p !== 0);
    if (!any.length) return null;
    return any.reduce((a, b) => a + b, 0) / any.length;
  }
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function elementaryIndices(prices, base) {
  const n = prices.length;
  const out = Array(n).fill(100);
  if (base == null || base === 0) return out;
  let prevP = null;
  let prevI = 100;
  for (let t = 0; t < n; t++) {
    const p = prices[t];
    if (p == null || p === 0) {
      out[t] = 100;
      continue;
    }
    let idx;
    if (t === 0 || prevP == null || prevP === 0) idx = (p / base) * 100;
    else idx = (p / prevP) * prevI;
    out[t] = idx;
    prevP = p;
    prevI = idx;
  }
  return out;
}

/**
 * Full UB recompute from products + structure.
 * Returns { indicesByRow, overall, groups, special }
 */
function recomputeUB(data) {
  const edit = data.ub_edit;
  if (!edit) throw new Error("ub_edit өгөгдөл алга — web-export дахин хийнэ үү");
  const n = data.months.length;
  const products = ubMergedProducts(data);
  const byRow = {};
  edit.structure.forEach((s) => {
    byRow[s.row] = s;
  });

  const indices = {};
  // elementary
  products.forEach((p) => {
    const base = basePrice(p.prices, edit.base_n || 12);
    indices[p.row] = elementaryIndices(p.prices, base);
  });

  // aggregate reverse row order
  const nodes = edit.structure.slice().sort((a, b) => b.row - a.row);
  nodes.forEach((node) => {
    if (node.kind === "elementary") return;
    const children = node.children || [];
    const parentW = node.weight || 0;
    const series = Array(n).fill(100);
    if (parentW === 0 || !children.length) {
      indices[node.row] = series;
      return;
    }
    for (let t = 0; t < n; t++) {
      let s = 0;
      children.forEach((c) => {
        const w = (byRow[c] && byRow[c].weight) || 0;
        const idx = indices[c] ? indices[c][t] : 100;
        s += w * idx;
      });
      series[t] = s / parentW;
    }
    indices[node.row] = series;
  });

  // major groups pack
  const majorRows = [8, 9, 209, 229, 316, 377, 461, 505, 554, 581, 628, 647, 663, 684];
  const groups = {};
  majorRows.forEach((r) => {
    const node = byRow[r];
    groups[String(r)] = {
      name: (node && node.name) || String(r),
      weight: node ? node.weight : r === 8 ? 100 : 0,
      weight_abs: 0,
      indices: (indices[r] || Array(n).fill(100)).map((x) =>
        Math.round(x * 1e6) / 1e6
      ),
    };
  });

  // special
  const special = {};
  const members = edit.special_members || {};
  const order = data.special_order || Object.keys(members);
  order.forEach((key) => {
    const rows = members[key] || [];
    let wSum = 0;
    const series = Array(n).fill(0);
    rows.forEach((r) => {
      const node = byRow[r];
      const w = node ? node.weight : 0;
      if (!w || !indices[r]) return;
      wSum += w;
      for (let t = 0; t < n; t++) series[t] += w * indices[r][t];
    });
    const idx = wSum
      ? series.map((s) => s / wSum)
      : Array(n).fill(100);
    const label =
      (data.special.ulaanbaatar &&
        data.special.ulaanbaatar[key] &&
        data.special.ulaanbaatar[key].label) ||
      key;
    special[key] = {
      label,
      weight: Math.round(wSum * 1e6) / 1e6,
      n_items: rows.filter((r) => byRow[r] && byRow[r].weight > 0).length,
      indices: idx.map((x) => Math.round(x * 1e6) / 1e6),
    };
  });

  const overall = (indices[8] || Array(n).fill(100)).map(
    (x) => Math.round(x * 1e6) / 1e6
  );

  return {
    indices,
    overall,
    groups,
    special,
    products,
  };
}

/** Apply recompute into live DATA (UB + national overall from aimags) */
function applyUBToData(data, recomputed) {
  if (!data.ulaanbaatar) data.ulaanbaatar = {};
  data.ulaanbaatar.overall = recomputed.overall;
  data.ulaanbaatar.groups = recomputed.groups;
  if (!data.special) data.special = {};
  data.special.ulaanbaatar = recomputed.special;

  if (data.aimags && data.aimags["20"]) {
    data.aimags["20"].overall = recomputed.overall;
  }

  // National overall ≈ weight-avg of aimags (when only UB prices change)
  if (data.aimags && data.national) {
    const n = data.months.length;
    const series = Array(n).fill(0);
    let wTot = 0;
    Object.keys(data.aimags).forEach((code) => {
      const a = data.aimags[code];
      const w = a.weight || 0;
      wTot += w;
      for (let t = 0; t < n; t++) {
        series[t] += w * (a.overall[t] || 100);
      }
    });
    if (wTot > 0) {
      data.national.overall = series.map((s) => Math.round((s / wTot) * 1e6) / 1e6);
      if (data.national.groups && data.national.groups["8"]) {
        data.national.groups["8"].indices = data.national.overall.slice();
      }
    }
  }
  data._ub_prices_dirty = true;
  data._ub_recomputed_at = new Date().toISOString();
  return data;
}

// ---------- UI ----------
function renderPriceEditor() {
  if (!DATA || !DATA.ub_edit) {
    const el = document.getElementById("priceEditor");
    if (el)
      el.innerHTML =
        "<p class='hint'>Үнэ оруулах өгөгдөл алга. Админ web-export хийнэ үү.</p>";
    return;
  }
  const months = DATA.months;
  const sel = document.getElementById("priceMonth");
  if (sel && !sel.options.length) {
    months.forEach((m) => {
      const o = document.createElement("option");
      o.value = m;
      o.textContent = m;
      sel.appendChild(o);
    });
    // default last month
    sel.value = months[months.length - 1];
  }
  fillPriceTable();
}

function fillPriceTable() {
  const month = document.getElementById("priceMonth").value;
  const q = (document.getElementById("priceSearch").value || "")
    .trim()
    .toLowerCase();
  const mi = DATA.months.indexOf(month);
  const products = ubMergedProducts(DATA);
  const ov = ubLoadOverrides();
  const tbody = document.querySelector("#tblPrices tbody");
  if (!tbody || mi < 0) return;

  let list = products;
  if (q) {
    list = products.filter(
      (p) =>
        (p.name || "").toLowerCase().includes(q) ||
        String(p.item_no || "").includes(q) ||
        String(p.row).includes(q)
    );
  }

  // only show products with weight > 0 or existing price (less clutter)
  const onlyW = document.getElementById("priceOnlyWeight");
  if (onlyW && onlyW.checked) {
    list = list.filter((p) => (p.weight || 0) > 0 || (p.prices[mi] != null && p.prices[mi] !== 0));
  }

  tbody.innerHTML = list
    .map((p) => {
      const cur = p.prices[mi];
      const prev = mi > 0 ? p.prices[mi - 1] : null;
      const edited = ov[String(p.row)] && ov[String(p.row)][month] != null;
      const disp = cur == null ? "" : cur;
      return `<tr class="${edited ? "price-edited" : ""}" data-row="${p.row}">
        <td>${p.item_no != null ? p.item_no : ""}</td>
        <td class="price-name">${escapeHtml(p.name)}</td>
        <td>${fmt(p.weight, 4)}</td>
        <td>${prev == null ? "—" : fmt(prev, 1)}</td>
        <td>
          <input type="number" class="price-input" min="0" step="0.1"
            data-row="${p.row}" data-month="${month}"
            value="${disp}" placeholder="—" />
        </td>
      </tr>`;
    })
    .join("");

  tbody.querySelectorAll(".price-input").forEach((inp) => {
    inp.addEventListener("change", onPriceInput);
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onPriceInput.call(inp);
        const tr = inp.closest("tr");
        const next = tr && tr.nextElementSibling;
        if (next) {
          const n = next.querySelector(".price-input");
          if (n) n.focus();
        }
      }
    });
  });

  const st = document.getElementById("priceStatus");
  if (st) {
    const nEdit = Object.keys(ov).length;
    st.textContent =
      month +
      " · " +
      list.length +
      " бараа · засагдсан " +
      nEdit +
      " нэр" +
      (DATA._ub_recomputed_at
        ? " · тооцоо: " + DATA._ub_recomputed_at.slice(0, 19)
        : "");
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function onPriceInput() {
  const row = this.getAttribute("data-row");
  const month = this.getAttribute("data-month");
  const raw = this.value.trim();
  const ov = ubLoadOverrides();
  if (!ov[row]) ov[row] = {};
  if (raw === "") {
    delete ov[row][month];
    if (!Object.keys(ov[row]).length) delete ov[row];
  } else {
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 0) {
      showStatus("Үнэ буруу: " + raw, "err");
      return;
    }
    ov[row][month] = n;
  }
  ubSaveOverrides(ov);
  this.closest("tr").classList.add("price-edited");
  const st = document.getElementById("priceStatus");
  if (st) st.textContent = "Хадгаллаа (local) · «Индекс тооцох» дарна уу";
}

function recomputeFromPrices() {
  if (!DATA || !DATA.ub_edit) {
    showStatus("ub_edit алга", "err");
    return;
  }
  try {
    showStatus("УБ индекс тооцоолж байна…", "info");
    const rec = recomputeUB(DATA);
    applyUBToData(DATA, rec);
    showStatus(
      "УБ индекс шинэчлэгдлээ. Үндсэн сараа сонгоод «Тооцох» / tab-уудаа харна уу.",
      "ok"
    );
    if (typeof render === "function") render();
    fillPriceTable();
  } catch (e) {
    showStatus("Алдаа: " + e.message, "err");
    console.error(e);
  }
}

function clearPriceEdits() {
  if (!confirm("УБ-ын вeb дээр оруулсан бүх үнийг устгах уу? (localStorage)")) return;
  ubClearOverrides();
  showStatus("Оруулсан үнэ цэвэрлэгдлээ. Хуудас дахин ачаална.", "info");
  location.reload();
}

function downloadPriceCSV() {
  if (!DATA || !DATA.ub_edit) return;
  const month = document.getElementById("priceMonth").value;
  const mi = DATA.months.indexOf(month);
  const products = ubMergedProducts(DATA);
  const lines = [["row", "item_no", "name", "weight", "period", "price"].join(",")];
  products.forEach((p) => {
    const price = p.prices[mi];
    const name = '"' + String(p.name).replace(/"/g, '""') + '"';
    lines.push(
      [p.row, p.item_no || "", name, p.weight, month, price == null ? "" : price].join(
        ","
      )
    );
  });
  const blob = new Blob(["\ufeff" + lines.join("\n")], {
    type: "text/csv;charset=utf-8",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "ub_prices_" + month + ".csv";
  a.click();
}

function downloadBundleJSON() {
  if (!DATA) return;
  // ensure latest recompute
  try {
    const rec = recomputeUB(DATA);
    applyUBToData(DATA, rec);
  } catch (_) {}
  const blob = new Blob([JSON.stringify(DATA)], {
    type: "application/json",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "cpi_bundle_ub_edited.json";
  a.click();
  showStatus("JSON татагдлаа — docs/data/cpi_bundle.json болгон солиод push хийж болно", "ok");
}

function importPriceCSV(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const text = String(reader.result || "");
    const lines = text.split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) {
      showStatus("CSV хоосон", "err");
      return;
    }
    const ov = ubLoadOverrides();
    let n = 0;
    for (let i = 1; i < lines.length; i++) {
      // simple CSV split
      const parts = lines[i].match(/("([^"]|"")*"|[^,]*)/g) || [];
      const cols = parts.map((p) => p.replace(/^"|"$/g, "").replace(/""/g, '"'));
      if (cols.length < 6) continue;
      const row = cols[0];
      const period = cols[4];
      const price = cols[5];
      if (!row || !period) continue;
      if (price === "") continue;
      const num = Number(price);
      if (!Number.isFinite(num)) continue;
      if (!ov[row]) ov[row] = {};
      ov[row][period] = num;
      n++;
    }
    ubSaveOverrides(ov);
    showStatus(n + " үнэ CSV-ээс орлоо. «Индекс тооцох» дарна уу.", "ok");
    fillPriceTable();
  };
  reader.readAsText(file, "UTF-8");
}
