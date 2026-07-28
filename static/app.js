const form = document.querySelector("#analyze-form");
const results = document.querySelector("#results");
const statusEl = document.querySelector("#status");
const template = document.querySelector("#card-template");
const screenerTemplate = document.querySelector("#screener-template");
const momentumTemplate = document.querySelector("#momentum-template");
const screenBtn = document.querySelector("#screen-btn");
const momentumBtn = document.querySelector("#momentum-btn");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusEl.textContent = "Mengambil data...";
  results.className = "results";
  results.innerHTML = "";

  const formData = new FormData(form);
  const options = Object.fromEntries([...formData.keys()].filter((key) => key !== "tickers").map((key) => [key, true]));

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers: formData.get("tickers"), options }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Gagal analisa.");

    payload.results.forEach((item) => results.appendChild(item.ok ? renderCard(item.data) : renderError(item)));
    statusEl.textContent = `${payload.results.length} saham`;
  } catch (error) {
    results.appendChild(renderError({ ticker: "ERROR", error: error.message }));
    statusEl.textContent = "Gagal";
  }
});

screenBtn.addEventListener("click", async () => {
  statusEl.textContent = "Screening...";
  results.className = "results";
  results.innerHTML = "";

  try {
    const response = await fetch("/api/screen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        maxTickers: Number(document.querySelector("#max-tickers").value || 1009),
        limit: Number(document.querySelector("#screen-limit").value || 15),
        mode: document.querySelector("#momentum-mode").value,
        relativeStrength: document.querySelector("#relative-strength").checked,
        accumulation: document.querySelector("#accumulation").checked,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Gagal screening.");

    results.appendChild(renderScreener(payload));
    statusEl.textContent = `${payload.qualified} lolos dari ${payload.checked}`;
  } catch (error) {
    results.appendChild(renderError({ ticker: "SCREENER", error: error.message }));
    statusEl.textContent = "Gagal";
  }
});

momentumBtn.addEventListener("click", async () => {
  statusEl.textContent = "Mencari momentum...";
  results.className = "results";
  results.innerHTML = "";

  try {
    const response = await fetch("/api/momentum", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        maxTickers: Number(document.querySelector("#max-tickers").value || 1009),
        limit: Number(document.querySelector("#screen-limit").value || 15),
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Gagal screening momentum.");

    results.appendChild(renderMomentum(payload));
    statusEl.textContent = `${payload.qualified} momentum dari ${payload.checked}`;
  } catch (error) {
    results.appendChild(renderError({ ticker: "MOMENTUM", error: error.message }));
    statusEl.textContent = "Gagal";
  }
});

function renderCard(data) {
  const node = template.content.firstElementChild.cloneNode(true);
  const recommendation = data.recommendation || "N/A";
  node.classList.add(recommendation.includes("BUY") ? "buy" : recommendation.includes("HOLD") ? "hold" : "avoid");
  node.querySelector("h3").textContent = data.ticker;
  node.querySelector(".meta").textContent = [data.name, data.sector, formatPrice(data.last_price)].filter(Boolean).join(" - ");
  node.querySelector(".badge").textContent = recommendation;
  node.querySelector('[data-key="technical"]').textContent = score(data.technical?.score);
  node.querySelector('[data-key="fundamental"]').textContent = score(data.fundamental?.score);
  node.querySelector('[data-key="liquidity"]').textContent = score(data.liquidity?.score);
  node.querySelector('[data-key="sentiment"]').textContent = score(data.sentiment?.skor);
  node.querySelector('[data-key="bandarmology"]').textContent = score(data.bandarmology?.skor);
  node.querySelector('[data-key="composite"]').textContent = score(data.composite_score);
  node.querySelector(".reason").textContent = data.reason || "";

  const flags = node.querySelector(".flags");
  (data.red_flags || []).forEach((flag) => {
    const li = document.createElement("li");
    li.textContent = flag;
    flags.appendChild(li);
  });
  if (!flags.children.length) flags.remove();

  node.querySelector(".signals").append(signalBlock("Teknikal", data.technical?.signals));
  node.querySelector(".signals").append(signalBlock("Fundamental", data.fundamental?.signals));
  if (data.liquidity) node.querySelector(".signals").append(liquidityBlock(data.liquidity));
  if (data.sentiment) node.querySelector(".signals").append(sentimentBlock(data.sentiment));
  node.querySelector(".signals").append(bandarmologyBlock(data.bandarmology));
  node.querySelector(".extras").append(extraBlock(data.extras || {}));
  return node;
}

function renderMomentum(payload) {
  const node = momentumTemplate.content.firstElementChild.cloneNode(true);
  const modeLabel = payload.mode === "preopen" ? "pre-open besok" : payload.mode === "session2" ? "sesi 2 / 13:30" : "intraday/jelang close";
  node.querySelector("h3").textContent = payload.mode === "preopen" ? "Pre-Open Watchlist" : payload.mode === "session2" ? "Top Gainer Sesi 2" : "Momentum Harian";
  node.querySelector(".meta").textContent = `${payload.qualified} kandidat ${modeLabel} dari ${payload.checked} ticker dicek`;
  const table = node.querySelector(".momentum-table");
  if (!payload.results.length) {
    table.textContent = "Belum ada kandidat momentum yang lolos filter.";
    return node;
  }

  table.innerHTML = `
    <div class="momentum-head">
      <b>Ticker</b><b>Skor</b><b>Status</b><b>Change</b><b>Vol</b><b>Value</b><b>Breakout</b><b>Sinyal</b>
    </div>
  `;
  payload.results.forEach((item) => {
    const momentum = item.momentum;
    const row = document.createElement("div");
    row.className = "momentum-row";
    row.innerHTML = `
      <b>${item.ticker}</b>
      <strong>${score(momentum.score)}</strong>
      <span>${momentum.status}</span>
      <span>${momentum.change_pct.toFixed(2)}%</span>
      <span>${momentum.volume_ratio.toFixed(2)}x</span>
      <span>${formatPrice(momentum.value_today)}</span>
      <span>${momentum.breakout_20d ? "Ya" : "Tidak"}</span>
      <span>${Object.values(momentum.signals || {}).join(", ")}</span>
    `;
    table.appendChild(row);
  });
  return node;
}

function renderScreener(payload) {
  const node = screenerTemplate.content.firstElementChild.cloneNode(true);
  node.querySelector(".meta").textContent = `${payload.qualified} kandidat lolos dari ${payload.checked} ticker dicek`;
  const table = node.querySelector(".screen-table");
  if (!payload.results.length) {
    table.textContent = "Belum ada saham yang lolos filter.";
    return node;
  }

  table.innerHTML = `
    <div class="screen-head">
      <b>Ticker</b><b>Rekomendasi</b><b>Komposit</b><b>Teknikal</b><b>Fundamental</b><b>Likuiditas</b><b>Bandar</b><b>Alasan</b>
    </div>
  `;
  payload.results.forEach((item) => {
    const row = document.createElement("div");
    row.className = "screen-row";
    row.innerHTML = `
      <b>${item.ticker}</b>
      <span>${item.recommendation}</span>
      <strong>${score(item.composite_score)}</strong>
      <span>${score(item.technical?.score)}</span>
      <span>${score(item.fundamental?.score)}</span>
      <span>${score(item.liquidity?.score)}</span>
      <span>${score(item.bandarmology?.skor)}</span>
      <span>${item.reason || ""}</span>
    `;
    table.appendChild(row);
  });
  return node;
}

function liquidityBlock(liquidity) {
  return signalBlock("Likuiditas", {
    Status: liquidity.status,
    "Avg Value 20D": formatPrice(liquidity.avg_value_20d),
    "Avg Volume 20D": Number(liquidity.avg_volume_20d || 0).toLocaleString("id-ID"),
  });
}

function signalBlock(title, signals = {}) {
  const wrap = document.createElement("section");
  wrap.innerHTML = `<h4>${title}</h4>`;
  Object.entries(signals).forEach(([key, value]) => {
    const p = document.createElement("p");
    p.innerHTML = `<b>${key}</b><span>${value}</span>`;
    wrap.appendChild(p);
  });
  return wrap;
}

function bandarmologyBlock(bandarmology) {
  const section = signalBlock("Bandarmologi", {
    Fase: bandarmology.fase,
    "OBV Trend": bandarmology.obv.obv_trend.toUpperCase(),
    MFI: `${bandarmology.mfi.mfi} - ${bandarmology.mfi.status}`,
    Divergensi: bandarmology.obv.divergensi || "Tidak ada",
  });
  [
    ["Akumulasi", bandarmology.akumulasi_3hari],
    ["Distribusi", bandarmology.distribusi_3hari],
  ].forEach(([label, signals]) => signals.forEach((item) => {
    const p = document.createElement("p");
    const heading = document.createElement("b");
    const detail = document.createElement("span");
    heading.textContent = `${label} ${item.tanggal}`;
    detail.textContent = `Harga ${item.harga}, vol ${item.vol_ratio}x - ${item.alasan.join(", ")}`;
    p.append(heading, detail);
    section.appendChild(p);
  }));
  return section;
}

function sentimentBlock(sentiment) {
  const section = signalBlock("Sentimen Berita", {
    Periode: `${sentiment.periode_hari || 30} hari terakhir`,
    Status: sentiment.status,
    Berita: `${sentiment.total} (${sentiment.positif} positif, ${sentiment.negatif} negatif, ${sentiment.netral} netral)`,
    Sumber: `${sentiment.sumber?.google_news || 0} Google News, ${sentiment.sumber?.kontan || 0} Kontan`,
    Confidence: `${(sentiment.confidence * 100).toFixed(1)}%`,
  });
  (sentiment.detail || []).forEach((item) => {
    const p = document.createElement("p");
    const label = document.createElement("b");
    const title = document.createElement("span");
    label.textContent = `${item.sentimen} (${(item.confidence * 100).toFixed(1)}%)`;
    title.textContent = item.judul;
    p.append(label, title);
    section.appendChild(p);
  });
  return section;
}

function extraBlock(extras) {
  const wrap = document.createElement("section");
  wrap.innerHTML = "<h4>Analisa Tambahan</h4>";
  if (!Object.keys(extras).length) {
    wrap.insertAdjacentHTML("beforeend", "<p><span>Tidak dipilih.</span></p>");
    return wrap;
  }
  Object.entries(extras).forEach(([key, value]) => {
    const p = document.createElement("p");
    p.innerHTML = `<b>${key}</b><span>${summarize(value)}</span>`;
    wrap.appendChild(p);
  });
  return wrap;
}

function renderError(item) {
  const div = document.createElement("article");
  div.className = "stock-card avoid";
  div.innerHTML = `<header><h3>${item.ticker}</h3><strong class="badge">ERROR</strong></header><p class="reason">${item.error}</p>`;
  return div;
}

function score(value) {
  return value === null || value === undefined ? "N/A" : Number(value).toFixed(1);
}

function formatPrice(value) {
  return value ? `Rp ${Number(value).toLocaleString("id-ID")}` : "";
}

function summarize(value) {
  if (value.total_trades !== undefined) return `${value.total_trades} trade, win rate ${value.win_rate ?? "N/A"}%`;
  if (value.expected_return_pct !== undefined) return `expected return ${value.expected_return_pct}%`;
  if (value.forecast_volatility !== undefined) return `forecast volatility ${value.forecast_volatility}`;
  if (value.atr !== undefined) return `ATR ${value.atr}, change ${value.atr_change_pct}%`;
  if (value.vwap !== undefined) return `VWAP ${value.vwap}, price vs VWAP ${value.price_vs_vwap_pct}%`;
  return JSON.stringify(value);
}
