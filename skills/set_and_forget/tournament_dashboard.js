(function () {
  const palette = ["#80ffdb", "#5390d9", "#fba2b0", "#64dfe0", "#7400b8"];
  const fallbackViewModel = {
    view_model_version: "1.0",
    generated_at: "2026-03-26T17:00:00+00:00",
    overview: {
      model_count: 4,
      tournament_entry_count: 28,
      settlement_count: 12,
      reflection_snapshot_count: 16,
    },
    leaderboard: [
      {
        model_id: "openrouter/anthropic/claude-sonnet-4.6",
        display_name: "claude-sonnet-4.6",
        leaderboard_rank: 1,
        cumulative_realized_pnl_r: -3.0,
        win_rate_percent: 0,
        invalid_output_count: 2,
        baseline_agreement_rate_percent: 100,
        average_confidence_score: 67,
        latest_decision: "BUY",
        latest_outcome_status: "stop_loss_hit",
        peer_rank_by_pnl: 1,
        peer_gap_to_best_r: 0,
        self_review: "Losses remain controlled, but selectivity has to improve before confidence should expand again.",
        equity_curve: [
          { recorded_at: "2026-03-26T15:00:00+00:00", equity_r: 0, outcome_status: "unsettled" },
          { recorded_at: "2026-03-26T15:30:00+00:00", equity_r: -1, outcome_status: "stop_loss_hit" },
          { recorded_at: "2026-03-26T16:00:00+00:00", equity_r: -2, outcome_status: "stop_loss_hit" },
          { recorded_at: "2026-03-26T16:30:00+00:00", equity_r: -3, outcome_status: "stop_loss_hit" },
        ],
      },
      {
        model_id: "openrouter/anthropic/claude-opus-4.6",
        display_name: "claude-opus-4.6",
        leaderboard_rank: 2,
        cumulative_realized_pnl_r: -3.0,
        win_rate_percent: 0,
        invalid_output_count: 2,
        baseline_agreement_rate_percent: 100,
        average_confidence_score: 70,
        latest_decision: "BUY",
        latest_outcome_status: "stop_loss_hit",
        peer_rank_by_pnl: 2,
        peer_gap_to_best_r: 0,
        self_review: "The contract is stable, but the trade filter is still too permissive after repeat stop-outs.",
        equity_curve: [
          { recorded_at: "2026-03-26T15:00:00+00:00", equity_r: 0, outcome_status: "unsettled" },
          { recorded_at: "2026-03-26T15:30:00+00:00", equity_r: -1, outcome_status: "stop_loss_hit" },
          { recorded_at: "2026-03-26T16:00:00+00:00", equity_r: -2, outcome_status: "stop_loss_hit" },
          { recorded_at: "2026-03-26T16:30:00+00:00", equity_r: -3, outcome_status: "stop_loss_hit" },
        ],
      },
      {
        model_id: "openrouter/minimax/minimax-m1",
        display_name: "minimax-m1",
        leaderboard_rank: 3,
        cumulative_realized_pnl_r: -3.0,
        win_rate_percent: 0,
        invalid_output_count: 2,
        baseline_agreement_rate_percent: 100,
        average_confidence_score: 63,
        latest_decision: "BUY",
        latest_outcome_status: "stop_loss_hit",
        peer_rank_by_pnl: 3,
        peer_gap_to_best_r: 0,
        self_review: "Outputs are contract-clean, but edge quality still lags the baseline and better-ranked peers.",
        equity_curve: [
          { recorded_at: "2026-03-26T15:00:00+00:00", equity_r: 0, outcome_status: "unsettled" },
          { recorded_at: "2026-03-26T15:30:00+00:00", equity_r: -1, outcome_status: "stop_loss_hit" },
          { recorded_at: "2026-03-26T16:00:00+00:00", equity_r: -2, outcome_status: "stop_loss_hit" },
          { recorded_at: "2026-03-26T16:30:00+00:00", equity_r: -3, outcome_status: "stop_loss_hit" },
        ],
      },
      {
        model_id: "openrouter/moonshotai/kimi-k2",
        display_name: "kimi-k2",
        leaderboard_rank: 4,
        cumulative_realized_pnl_r: -1.0,
        win_rate_percent: 0,
        invalid_output_count: 5,
        baseline_agreement_rate_percent: 85.71,
        average_confidence_score: 41,
        latest_decision: "BUY",
        latest_outcome_status: "stop_loss_hit",
        peer_rank_by_pnl: 4,
        peer_gap_to_best_r: 2,
        self_review: "Contract reliability improved, but invalid outputs still keep this model behind the field.",
        equity_curve: [
          { recorded_at: "2026-03-26T15:00:00+00:00", equity_r: 0, outcome_status: "unsettled" },
          { recorded_at: "2026-03-26T15:30:00+00:00", equity_r: 0, outcome_status: "unsettled" },
          { recorded_at: "2026-03-26T16:00:00+00:00", equity_r: 0, outcome_status: "unsettled" },
          { recorded_at: "2026-03-26T16:30:00+00:00", equity_r: -1, outcome_status: "stop_loss_hit" },
        ],
      },
    ],
    charts: { equity_curves: [], performance_bars: [] },
    recent_decisions: [
      {
        model_id: "openrouter/moonshotai/kimi-k2",
        decision: "BUY",
        confidence_score: 58,
        summary: "Kimi returned a valid contract output after retry hardening, but still took the same losing continuation setup.",
        primary_decision: "BUY",
        recorded_at: "2026-03-26T16:57:00+00:00",
        reason_codes: ["HIGHER_TF_ALIGNED", "RR_VALID"],
      },
      {
        model_id: "openrouter/anthropic/claude-sonnet-4.6",
        decision: "BUY",
        confidence_score: 62,
        summary: "Sonnet stayed aligned with the baseline and delivered a contract-valid paper verdict.",
        primary_decision: "BUY",
        recorded_at: "2026-03-26T16:57:00+00:00",
        reason_codes: ["HIGHER_TF_ALIGNED", "CONFIRMATION_PRESENT"],
      },
      {
        model_id: "openrouter/anthropic/claude-opus-4.6",
        decision: "BUY",
        confidence_score: 66,
        summary: "Opus preserved the objective setup reading, but the market outcome still stopped the trade.",
        primary_decision: "BUY",
        recorded_at: "2026-03-26T16:57:00+00:00",
        reason_codes: ["HIGHER_TF_ALIGNED", "AOI_CONFLUENCE_STRONG"],
      },
      {
        model_id: "openrouter/minimax/minimax-m1",
        decision: "BUY",
        confidence_score: 59,
        summary: "Minimax accepted the reward-to-risk profile and remained contract-clean.",
        primary_decision: "BUY",
        recorded_at: "2026-03-26T16:57:00+00:00",
        reason_codes: ["HIGHER_TF_ALIGNED", "RR_VALID"],
      },
    ],
  };

  function formatModelName(modelId, displayName) {
    if (displayName) {
      return displayName;
    }
    const tail = String(modelId || "").split("/").pop();
    return tail || "unknown-model";
  }

  function formatDateTime(value) {
    if (!value) {
      return "No timestamp";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatPercent(value) {
    if (value === null || value === undefined) {
      return "n/a";
    }
    return `${Number(value).toFixed(1)}%`;
  }

  function formatR(value) {
    if (value === null || value === undefined) {
      return "n/a";
    }
    const number = Number(value);
    if (Number.isNaN(number)) {
      return "n/a";
    }
    return `${number > 0 ? "+" : ""}${number.toFixed(1)}R`;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function getColor(index) {
    return palette[index % palette.length];
  }

  function decisionClassName(decision) {
    if (decision === "BUY") {
      return "background: rgba(128, 255, 219, 0.18); color: #80ffdb; border: 1px solid rgba(128, 255, 219, 0.28);";
    }
    if (decision === "SELL") {
      return "background: rgba(251, 162, 176, 0.18); color: #fba2b0; border: 1px solid rgba(251, 162, 176, 0.28);";
    }
    return "background: rgba(83, 144, 217, 0.18); color: #64dfe0; border: 1px solid rgba(100, 223, 224, 0.28);";
  }

  function statusStyle(status) {
    if (status === "take_profit_hit") {
      return "background: rgba(128, 255, 219, 0.18); color: #80ffdb; border: 1px solid rgba(128, 255, 219, 0.28);";
    }
    if (status === "stop_loss_hit") {
      return "background: rgba(251, 162, 176, 0.18); color: #fba2b0; border: 1px solid rgba(251, 162, 176, 0.28);";
    }
    if (status === "unsettled" || status === "pending") {
      return "background: rgba(83, 144, 217, 0.18); color: #64dfe0; border: 1px solid rgba(100, 223, 224, 0.28);";
    }
    return "background: rgba(255, 255, 255, 0.08); color: #f6fbff; border: 1px solid rgba(255, 255, 255, 0.12);";
  }

  function setOverview(data, sourceLabel) {
    const sourceEl = document.getElementById("data-source");
    const generatedAtEl = document.getElementById("generated-at");
    const overviewCardsEl = document.getElementById("overview-cards");
    const overview = data.overview || {};
    const cards = [
      {
        label: "Models",
        value: overview.model_count || 0,
        copy: "Active leaderboard participants",
      },
      {
        label: "Entries",
        value: overview.tournament_entry_count || 0,
        copy: "Logged tournament decisions",
      },
      {
        label: "Settlements",
        value: overview.settlement_count || 0,
        copy: "Closed or classified shadow outcomes",
      },
      {
        label: "Reflections",
        value: overview.reflection_snapshot_count || 0,
        copy: "Prompt-ready self-review snapshots",
      },
    ];

    sourceEl.textContent = sourceLabel;
    generatedAtEl.textContent = `Last build: ${formatDateTime(data.generated_at)}`;
    overviewCardsEl.innerHTML = cards
      .map(
        (card) => `
          <article class="metric-card">
            <div class="metric-value">${escapeHtml(card.value)}</div>
            <div class="metric-label">${escapeHtml(card.label)}</div>
            <div class="metric-copy">${escapeHtml(card.copy)}</div>
          </article>
        `
      )
      .join("");
  }

  function renderLeaderboard(data) {
    const el = document.getElementById("leaderboard-grid");
    const items = data.leaderboard || [];
    if (!items.length) {
      el.innerHTML = '<div class="empty-state">No leaderboard rows were found in the current dashboard view model.</div>';
      return;
    }

    el.innerHTML = items
      .map((item, index) => {
        const color = getColor(index);
        const rankStyle = `background: ${color}22; color: ${color}; border: 1px solid ${color}55;`;
        return `
          <article class="leader-card">
            <div class="leader-topline">
              <span class="rank-pill" style="${rankStyle}">#${escapeHtml(item.leaderboard_rank || index + 1)}</span>
              <span class="status-pill" style="${statusStyle(item.latest_outcome_status)}">${escapeHtml(item.latest_outcome_status || "unsettled")}</span>
            </div>
            <div class="model-name">${escapeHtml(formatModelName(item.model_id, item.display_name))}</div>
            <div class="leader-grid">
              <div class="leader-stat">Realized PnL<strong>${escapeHtml(formatR(item.cumulative_realized_pnl_r))}</strong></div>
              <div class="leader-stat">Win Rate<strong>${escapeHtml(formatPercent(item.win_rate_percent))}</strong></div>
              <div class="leader-stat">Agreement<strong>${escapeHtml(formatPercent(item.baseline_agreement_rate_percent))}</strong></div>
              <div class="leader-stat">Invalid Outputs<strong>${escapeHtml(item.invalid_output_count || 0)}</strong></div>
            </div>
            <div class="leader-review">${escapeHtml(item.self_review || "No reflection snapshot available yet.")}</div>
          </article>
        `;
      })
      .join("");
  }

  function renderPerformanceBars(data) {
    const el = document.getElementById("performance-bars");
    const items = data.leaderboard || [];
    if (!items.length) {
      el.innerHTML = '<div class="empty-state">No comparison data available.</div>';
      return;
    }

    const maxPnlMagnitude = Math.max(
      1,
      ...items.map((item) => Math.abs(Number(item.cumulative_realized_pnl_r || 0)))
    );

    el.innerHTML = items
      .map((item, index) => {
        const color = getColor(index);
        const pnl = Number(item.cumulative_realized_pnl_r || 0);
        const width = `${Math.max(8, (Math.abs(pnl) / maxPnlMagnitude) * 100)}%`;
        return `
          <article class="bar-card">
            <div class="bar-topline">
              <strong>${escapeHtml(formatModelName(item.model_id, item.display_name))}</strong>
              <span>${escapeHtml(formatR(pnl))}</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill" style="width: ${width}; background: linear-gradient(90deg, ${color}, ${color}88);"></div>
            </div>
            <div class="bar-grid">
              <div class="bar-meta">Win Rate<strong>${escapeHtml(formatPercent(item.win_rate_percent))}</strong></div>
              <div class="bar-meta">Agreement<strong>${escapeHtml(formatPercent(item.baseline_agreement_rate_percent))}</strong></div>
              <div class="bar-meta">Invalid<strong>${escapeHtml(item.invalid_output_count || 0)}</strong></div>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderRecentDecisions(data) {
    const el = document.getElementById("recent-decisions");
    const items = data.recent_decisions || [];
    if (!items.length) {
      el.innerHTML = '<div class="empty-state">No recent decisions were found.</div>';
      return;
    }

    el.innerHTML = items
      .map((item) => {
        const aligned = item.decision === item.primary_decision ? "Aligned" : "Diverged";
        const alignedColor = item.decision === item.primary_decision ? "#80ffdb" : "#fba2b0";
        return `
          <article class="decision-card">
            <div class="decision-topline">
              <div class="decision-model">${escapeHtml(formatModelName(item.model_id, item.display_name))}</div>
              <span class="decision-pill" style="${decisionClassName(item.decision)}">${escapeHtml(item.decision || "WAIT")}</span>
            </div>
            <div class="decision-summary">${escapeHtml(item.summary || "No summary available.")}</div>
            <div class="decision-meta">
              <div>Confidence<strong>${escapeHtml(item.confidence_score ?? "n/a")}</strong></div>
              <div>Primary<strong style="color:${alignedColor};">${escapeHtml(item.primary_decision || "n/a")} · ${aligned}</strong></div>
              <div>Recorded<strong>${escapeHtml(formatDateTime(item.recorded_at))}</strong></div>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderEquityLegend(data) {
    const el = document.getElementById("equity-legend");
    const items = data.leaderboard || [];
    el.innerHTML = items
      .map(
        (item, index) => `
          <span class="legend-pill">
            <span class="legend-dot" style="background:${getColor(index)};"></span>
            ${escapeHtml(formatModelName(item.model_id, item.display_name))}
          </span>
        `
      )
      .join("");
  }

  function renderEquityChart(data) {
    const host = document.getElementById("equity-chart");
    const items = data.leaderboard || [];
    if (!items.length) {
      host.innerHTML = '<div class="empty-state">No equity curve points were found in the current view model.</div>';
      return;
    }

    const allPoints = items.flatMap((item) => item.equity_curve || []);
    if (!allPoints.length) {
      host.innerHTML = '<div class="empty-state">Equity curve points are missing for the current dataset.</div>';
      return;
    }

    const width = 880;
    const height = 360;
    const padding = { top: 24, right: 24, bottom: 40, left: 52 };
    const minY = Math.min(0, ...allPoints.map((point) => Number(point.equity_r || 0)));
    const maxY = Math.max(0, ...allPoints.map((point) => Number(point.equity_r || 0)));
    const rangeY = Math.max(1, maxY - minY);
    const xMaxCount = Math.max(...items.map((item) => (item.equity_curve || []).length), 1);

    const mapX = (index, count) => {
      const span = width - padding.left - padding.right;
      if (count <= 1) {
        return padding.left + span / 2;
      }
      return padding.left + (span * index) / (count - 1);
    };

    const mapY = (value) => {
      const span = height - padding.top - padding.bottom;
      return padding.top + ((maxY - value) / rangeY) * span;
    };

    const gridValues = [maxY, (maxY + minY) / 2, minY];
    const gridLines = gridValues
      .map((value) => {
        const y = mapY(value);
        return `
          <line class="axis-grid" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}"></line>
          <text class="axis-tick" x="${padding.left - 10}" y="${y + 4}" text-anchor="end">${escapeHtml(formatR(value))}</text>
        `;
      })
      .join("");

    const xTicks = Array.from({ length: xMaxCount }, (_, index) => {
      const x = mapX(index, xMaxCount);
      return `<text class="axis-tick" x="${x}" y="${height - 12}" text-anchor="middle">T${index + 1}</text>`;
    }).join("");

    const series = items
      .map((item, index) => {
        const points = item.equity_curve || [];
        const color = getColor(index);
        const polyline = points
          .map((point, pointIndex) => `${mapX(pointIndex, points.length)},${mapY(Number(point.equity_r || 0))}`)
          .join(" ");
        const markers = points
          .map((point, pointIndex) => {
            const x = mapX(pointIndex, points.length);
            const y = mapY(Number(point.equity_r || 0));
            return `<circle cx="${x}" cy="${y}" r="4" fill="${color}" stroke="#f6fbff" stroke-width="1"></circle>`;
          })
          .join("");
        return `
          <g style="color:${color};">
            <polyline class="line-shadow" fill="none" stroke="${color}" stroke-width="3.5" points="${polyline}"></polyline>
            ${markers}
          </g>
        `;
      })
      .join("");

    host.innerHTML = `
      <svg class="chart-shell" viewBox="0 0 ${width} ${height}" role="img" aria-label="Tournament equity curves">
        ${gridLines}
        <line class="axis-grid" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"></line>
        ${xTicks}
        <text class="axis-label" x="${padding.left}" y="16">Realized PnL (R)</text>
        ${series}
      </svg>
    `;
  }

  async function loadViewModel() {
    const params = new URLSearchParams(window.location.search);
    const requestedPath = params.get("data") || "./openclaw_tournament_dashboard_view_model.json";
    try {
      const response = await fetch(requestedPath, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      return {
        data: payload,
        sourceLabel: `Live view model · ${requestedPath}`,
      };
    } catch (error) {
      return {
        data: fallbackViewModel,
        sourceLabel: `Fallback demo dataset · ${requestedPath} unavailable`,
      };
    }
  }

  async function main() {
    const { data, sourceLabel } = await loadViewModel();
    setOverview(data, sourceLabel);
    renderEquityLegend(data);
    renderEquityChart(data);
    renderLeaderboard(data);
    renderPerformanceBars(data);
    renderRecentDecisions(data);
  }

  main();
})();
