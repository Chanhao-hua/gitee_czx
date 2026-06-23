const refreshButton = document.getElementById("refresh-btn");
const refreshStatus = document.getElementById("refresh-status");
const schedulerPill = document.getElementById("scheduler-pill");
const nextRun = document.getElementById("next-run");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const resultPanel = document.getElementById("result-panel");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-CN");
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN");
}

function renderMetrics(metrics) {
  const cards = [
    ["热门游戏", metrics.game_count, "当前数据库游戏条目"],
    ["B站分区", metrics.bilibili_area_count, "直播热度数据"],
    ["热度峰值", formatNumber(metrics.last_bilibili_peak), "当前最高在线"],
  ];
  document.getElementById("metrics-grid").innerHTML = cards.map(renderMetricCard).join("");
}

function renderMetricCard([label, value, sub]) {
  return `
    <article class="metric-card">
      <p class="metric-label">${escapeHtml(label)}</p>
      <div class="metric-value">${escapeHtml(value)}</div>
      <p class="metric-sub">${escapeHtml(sub)}</p>
    </article>
  `;
}

function renderBatchStatus(status) {
  document.getElementById("batch-panel").innerHTML = status.datasets
    .map((item) =>
      renderMetricCard([
        item.label,
        formatNumber(item.count),
        item.updated_at ? `更新：${formatDate(item.updated_at)}` : "等待首次爬取",
      ]),
    )
    .join("");
}

function renderRuns(runs) {
  document.getElementById("source-runs").innerHTML = runs
    .map((run) => {
      const ok = run.status === "success";
      return `
        <article class="source-run">
          <div class="card-title-row">
            <strong>${escapeHtml(run.source)}</strong>
            <span class="status-pill ${ok ? "status-success" : "status-failed"}">${escapeHtml(run.status)}</span>
          </div>
          <div class="meta-row">
            <span>记录：${run.record_count ?? 0}</span>
            <span>结束：${escapeHtml(run.finished_at || "-")}</span>
          </div>
          ${run.error_message ? `<p class="muted small-text">错误：${escapeHtml(run.error_message)}</p>` : ""}
        </article>
      `;
    })
    .join("");
}

function renderHotGames(games) {
  document.getElementById("hot-games").innerHTML = games
    .slice(0, 12)
    .map(
      (game) => `
        <article class="game-card">
          ${game.header_image ? `<img src="${escapeHtml(game.header_image)}" alt="${escapeHtml(game.name)} 封面" loading="lazy" />` : ""}
          <div class="game-card-body">
            <div class="card-title-row">
              <h3>${escapeHtml(game.name)}</h3>
              <span class="card-rank">#${game.rank_index}</span>
            </div>
            <p class="description">${escapeHtml(game.short_description || "暂无简介")}</p>
            <div class="meta-row">
              <span>${escapeHtml(game.source_site || "静态游戏目录")}</span>
              <span>${escapeHtml(game.platforms || "PC")}</span>
              <span>${escapeHtml(formatDate(game.scraped_at))}</span>
            </div>
            <div class="card-actions">
              <button type="button" class="link-btn" data-game="${escapeHtml(game.name)}">查攻略</button>
              <a href="${escapeHtml(game.detail_url || game.source_url)}" target="_blank" rel="noreferrer">来源页面</a>
            </div>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderBilibili(areas) {
  const peak = Math.max(...areas.map((item) => item.online), 1);
  document.getElementById("bilibili-list").innerHTML = areas
    .slice(0, 8)
    .map(
      (area) => `
        <article class="data-card">
          <div class="card-title-row">
            <strong>${escapeHtml(area.area_name)}</strong>
            <span class="card-rank">${formatNumber(area.online)}</span>
          </div>
          <div class="meta-row">
            <span>${escapeHtml(area.parent_area_name)}</span>
            <span>${escapeHtml(area.streamer_name)}</span>
          </div>
          <p class="muted small-text">${escapeHtml(area.room_title)}</p>
          <div class="bar-track"><div class="bar-fill" style="width:${Math.max(8, (area.online / peak) * 100)}%"></div></div>
        </article>
      `,
    )
    .join("");
}

function renderResult(payload) {
  const { game, live_area: liveArea, diagnosis, videos } = payload;
  resultPanel.classList.remove("hidden");
  resultPanel.innerHTML = `
    <section class="result-main">
      ${game.header_image ? `<img src="${escapeHtml(game.header_image)}" alt="${escapeHtml(game.name)} 封面" />` : ""}
      <div>
        <p class="eyebrow">搜索结果</p>
        <h2>${escapeHtml(game.name)}</h2>
        <p class="description">${escapeHtml(game.short_description)}</p>
        <div class="meta-row">
          <span>来源：${escapeHtml(game.source_site || "静态游戏目录")}</span>
          <span>平台：${escapeHtml(game.platforms || "PC")}</span>
          <span>采集：${escapeHtml(formatDate(game.scraped_at))}</span>
        </div>
        <div class="card-actions">
          <a href="${escapeHtml(game.detail_url || game.source_url)}" target="_blank" rel="noreferrer">打开来源页面</a>
          ${liveArea ? `<a href="${escapeHtml(liveArea.room_url)}" target="_blank" rel="noreferrer">查看 B站直播间</a>` : ""}
        </div>
      </div>
    </section>
    <section class="diagnosis-card">
      <strong>${escapeHtml(diagnosis.label)}</strong>
      <p>${escapeHtml(diagnosis.summary)}</p>
      <p>${escapeHtml(diagnosis.advice)}</p>
    </section>
    <section>
      <div class="section-head compact">
        <div>
          <h2>攻略视频</h2>
          <p class="muted">Bilibili 搜索「${escapeHtml(game.name)} 攻略」</p>
        </div>
      </div>
      <div class="video-grid">
        ${videos
          .map(
            (video) => `
              <a class="video-card" href="${escapeHtml(video.video_url)}" target="_blank" rel="noreferrer">
                ${video.cover_url ? `<img src="${escapeHtml(video.cover_url)}" alt="" loading="lazy" />` : ""}
                <strong>${escapeHtml(video.title)}</strong>
                <span>${escapeHtml(video.author)} · ${escapeHtml(video.stats)}</span>
              </a>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderError(message) {
  resultPanel.classList.remove("hidden");
  resultPanel.innerHTML = `<section class="diagnosis-card error"><strong>没有找到结果</strong><p>${escapeHtml(message)}</p></section>`;
}

async function loadDashboard() {
  const response = await fetch("/api/dashboard");
  const data = await response.json();
  renderMetrics(data.metrics);
  renderRuns(data.source_runs);
  renderHotGames(data.games || data.steam_games || []);
  renderBilibili(data.bilibili_areas);
  document.getElementById("generated-at").textContent = `数据库生成时间：${formatDate(data.generated_at)}`;
}

async function loadSchedulerStatus() {
  const [metaResponse, batchResponse] = await Promise.all([fetch("/api/meta"), fetch("/api/batch-status")]);
  const meta = await metaResponse.json();
  const batch = await batchResponse.json();
  schedulerPill.textContent = meta.scheduler_running ? "运行中" : "未启动";
  schedulerPill.className = `status-pill ${meta.scheduler_running ? "status-success" : "status-failed"}`;
  const job = meta.jobs?.[0];
  nextRun.textContent = job?.next_run_time ? `下次自动爬取：${formatDate(job.next_run_time)}` : "暂无下一次任务时间";
  renderBatchStatus(batch);
}

async function searchGame(gameName) {
  const query = gameName.trim();
  if (!query) return;
  refreshStatus.textContent = `正在聚合「${query}」的信息和攻略视频...`;
  resultPanel.classList.add("hidden");
  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const payload = await response.json();
    if (!response.ok) {
      renderError(payload.error || "搜索失败");
      return;
    }
    renderResult(payload);
    refreshStatus.textContent = "搜索完成。";
  } catch (error) {
    renderError(`搜索失败：${error}`);
  }
}

async function triggerRefresh() {
  refreshButton.disabled = true;
  refreshStatus.textContent = "正在爬取三类数据源并清洗去重，请稍等...";
  try {
    const response = await fetch("/api/refresh", { method: "POST" });
    const payload = await response.json();
    const summary = payload.datasets?.map((item) => `${item.label}${item.cleaned_count}条`).join("，");
    refreshStatus.textContent = summary ? `${payload.message}：${summary}` : payload.message || "爬取完成";
    await Promise.all([loadDashboard(), loadSchedulerStatus()]);
  } catch (error) {
    refreshStatus.textContent = `爬取失败：${error}`;
  } finally {
    refreshButton.disabled = false;
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchGame(searchInput.value);
});

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-game]");
  if (!target) return;
  searchInput.value = target.dataset.game;
  searchGame(target.dataset.game);
  window.scrollTo({ top: 0, behavior: "smooth" });
});

refreshButton.addEventListener("click", triggerRefresh);
Promise.all([loadDashboard(), loadSchedulerStatus()]);
setInterval(loadDashboard, 30000);
setInterval(loadSchedulerStatus, 30000);
