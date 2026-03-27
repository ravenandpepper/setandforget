(function () {
  const palette = ["#00ffaa", "#4d9fff", "#ff4d6a", "#b44dff", "#ff9f43", "#00e5ff"];

  const fallbackViewModel = {
    view_model_version: "2.0",
    generated_at: "2026-03-26T17:00:00+00:00",
    overview: {
      model_count: 4,
      tournament_entry_count: 28,
      settlement_count: 12,
      reflection_snapshot_count: 16,
      open_trades: 3,
      total_gross_pnl_eur: -312.5,
      total_net_pnl_eur: -347.8,
      total_costs_eur: 35.3,
      best_winrate: 42.0,
    },
    leaderboard: [
      {
        model_id: "openrouter/anthropic/claude-sonnet-4.6",
        display_name: "claude-sonnet-4.6",
        leaderboard_rank: 1,
        cumulative_realized_pnl_r: -3.0,
        net_pnl_r: -3.4,
        gross_pnl_eur: -150.0,
        net_pnl_eur: -168.5,
        total_costs_eur: 18.5,
        win_rate_percent: 0,
        invalid_output_count: 2,
        baseline_agreement_rate_percent: 100,
        average_confidence_score: 67,
        latest_decision: "BUY",
        latest_outcome_status: "stop_loss_hit",
        total_trades: 7,
        buy_count: 5,
        sell_count: 2,
        wait_count: 3,
        nogo_count: 0,
        open_trades: 1,
        max_drawdown_r: -3.0,
        cost_per_trade_eur: 2.64,
        costs_as_pct_of_gross: 12.3,
        spread_cost_eur: 10.5,
        commission_cost_eur: 3.5,
        swap_cost_eur: 2.8,
        slippage_cost_eur: 1.7,
        self_review: "Losses remain controlled, but selectivity has to improve before confidence should expand again.",
        equity_curve: [
          { recorded_at: "2026-03-26T15:00:00+00:00", equity_r: 0 },
          { recorded_at: "2026-03-26T15:30:00+00:00", equity_r: -1 },
          { recorded_at: "2026-03-26T16:00:00+00:00", equity_r: -2 },
          { recorded_at: "2026-03-26T16:30:00+00:00", equity_r: -3 },
        ],
      },
      {
        model_id: "openrouter/anthropic/claude-opus-4.6",
        display_name: "claude-opus-4.6",
        leaderboard_rank: 2,
        cumulative_realized_pnl_r: -3.0,
        net_pnl_r: -3.6,
        gross_pnl_eur: -150.0,
        net_pnl_eur: -172.0,
        total_costs_eur: 22.0,
        win_rate_percent: 0,
        invalid_output_count: 2,
        baseline_agreement_rate_percent: 100,
        average_confidence_score: 70,
        latest_decision: "BUY",
        latest_outcome_status: "stop_loss_hit",
        total_trades: 7,
        buy_count: 6,
        sell_count: 1,
        wait_count: 2,
        nogo_count: 0,
        open_trades: 1,
        max_drawdown_r: -3.0,
        cost_per_trade_eur: 3.14,
        costs_as_pct_of_gross: 14.7,
        spread_cost_eur: 12.0,
        commission_cost_eur: 4.2,
        swap_cost_eur: 3.5,
        slippage_cost_eur: 2.3,
        self_review: "The contract is stable, but the trade filter is still too permissive after repeat stop-outs.",
        equity_curve: [
          { recorded_at: "2026-03-26T15:00:00+00:00", equity_r: 0 },
          { recorded_at: "2026-03-26T15:30:00+00:00", equity_r: -1 },
          { recorded_at: "2026-03-26T16:00:00+00:00", equity_r: -2 },
          { recorded_at: "2026-03-26T16:30:00+00:00", equity_r: -3 },
        ],
      },
      {
        model_id: "openrouter/minimax/minimax-m1",
        display_name: "minimax-m1",
        leaderboard_rank: 3,
        cumulative_realized_pnl_r: -3.0,
        net_pnl_r: -3.3,
        gross_pnl_eur: -150.0,
        net_pnl_eur: -165.8,
        total_costs_eur: 15.8,
        win_rate_percent: 0,
        invalid_output_count: 2,
        baseline_agreement_rate_percent: 100,
        average_confidence_score: 63,
        latest_decision: "BUY",
        latest_outcome_status: "stop_loss_hit",
        total_trades: 7,
        buy_count: 4,
        sell_count: 3,
        wait_count: 4,
        nogo_count: 1,
        open_trades: 0,
        max_drawdown_r: -3.0,
        cost_per_trade_eur: 2.26,
        costs_as_pct_of_gross: 10.5,
        spread_cost_eur: 8.8,
        commission_cost_eur: 2.8,
        swap_cost_eur: 2.4,
        slippage_cost_eur: 1.8,
        self_review: "Outputs are contract-clean, but edge quality still lags the baseline and better-ranked peers.",
        equity_curve: [
          { recorded_at: "2026-03-26T15:00:00+00:00", equity_r: 0 },
          { recorded_at: "2026-03-26T15:30:00+00:00", equity_r: -1 },
          { recorded_at: "2026-03-26T16:00:00+00:00", equity_r: -2 },
          { recorded_at: "2026-03-26T16:30:00+00:00", equity_r: -3 },
        ],
      },
      {
        model_id: "openrouter/moonshotai/kimi-k2",
        display_name: "kimi-k2",
        leaderboard_rank: 4,
        cumulative_realized_pnl_r: -1.0,
        net_pnl_r: -1.2,
        gross_pnl_eur: -50.0,
        net_pnl_eur: -59.5,
        total_costs_eur: 9.5,
        win_rate_percent: 0,
        invalid_output_count: 5,
        baseline_agreement_rate_percent: 85.71,
        average_confidence_score: 41,
        latest_decision: "BUY",
        latest_outcome_status: "stop_loss_hit",
        total_trades: 3,
        buy_count: 2,
        sell_count: 0,
        wait_count: 8,
        nogo_count: 2,
        open_trades: 1,
        max_drawdown_r: -1.0,
        cost_per_trade_eur: 3.17,
        costs_as_pct_of_gross: 19.0,
        spread_cost_eur: 5.2,
        commission_cost_eur: 1.8,
        swap_cost_eur: 1.5,
        slippage_cost_eur: 1.0,
        self_review: "Contract reliability improved, but invalid outputs still keep this model behind the field.",
        equity_curve: [
          { recorded_at: "2026-03-26T15:00:00+00:00", equity_r: 0 },
          { recorded_at: "2026-03-26T15:30:00+00:00", equity_r: 0 },
          { recorded_at: "2026-03-26T16:00:00+00:00", equity_r: 0 },
          { recorded_at: "2026-03-26T16:30:00+00:00", equity_r: -1 },
        ],
      },
    ],
    pair_performance: [
      { pair: "EUR/USD", trades: 8, wins: 2, losses: 4, pending: 2, net_pnl_r: -1.8, best_model: "claude-sonnet-4.6" },
      { pair: "GBP/USD", trades: 6, wins: 1, losses: 3, pending: 2, net_pnl_r: -2.2, best_model: "kimi-k2" },
      { pair: "USD/JPY", trades: 5, wins: 0, losses: 4, pending: 1, net_pnl_r: -3.1, best_model: "minimax-m1" },
      { pair: "AUD/USD", trades: 3, wins: 1, losses: 1, pending: 1, net_pnl_r: -0.4, best_model: "claude-opus-4.6" },
      { pair: "EUR/GBP", trades: 4, wins: 2, losses: 1, pending: 1, net_pnl_r: 0.6, best_model: "claude-sonnet-4.6" },
      { pair: "NZD/USD", trades: 2, wins: 0, losses: 2, pending: 0, net_pnl_r: -1.8, best_model: "minimax-m1" },
    ],
    recent_decisions: [
      {
        model_id: "openrouter/moonshotai/kimi-k2",
        display_name: "kimi-k2",
        decision: "BUY",
        confidence_score: 58,
        summary: "Kimi returned a valid contract output after retry hardening, but still took the same losing continuation setup.",
        primary_decision: "BUY",
        recorded_at: "2026-03-26T16:57:00+00:00",
        reason_codes: ["HIGHER_TF_ALIGNED", "RR_VALID"],
      },
      {
        model_id: "openrouter/anthropic/claude-sonnet-4.6",
        display_name: "claude-sonnet-4.6",
        decision: "BUY",
        confidence_score: 62,
        summary: "Sonnet stayed aligned with the baseline and delivered a contract-valid paper verdict.",
        primary_decision: "BUY",
        recorded_at: "2026-03-26T16:57:00+00:00",
        reason_codes: ["HIGHER_TF_ALIGNED", "CONFIRMATION_PRESENT"],
      },
      {
        model_id: "openrouter/anthropic/claude-opus-4.6",
        display_name: "claude-opus-4.6",
        decision: "BUY",
        confidence_score: 66,
        summary: "Opus preserved the objective setup reading, but the market outcome still stopped the trade.",
        primary_decision: "BUY",
        recorded_at: "2026-03-26T16:57:00+00:00",
        reason_codes: ["HIGHER_TF_ALIGNED", "AOI_CONFLUENCE_STRONG"],
      },
      {
        model_id: "openrouter/minimax/minimax-m1",
        display_name: "minimax-m1",
        decision: "WAIT",
        confidence_score: 34,
        summary: "Minimax opted to sit this one out - low confidence on the continuation after three consecutive stop-outs.",
        primary_decision: "BUY",
        recorded_at: "2026-03-26T16:57:00+00:00",
        reason_codes: ["LOW_CONFIDENCE", "REPEAT_LOSS_STREAK"],
      },
    ],
  };

  function esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function num(value) {
    if (value === null || value === undefined || value === "") {
      return null;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function modelName(modelId, displayName) {
    return displayName || String(modelId || "").split("/").pop() || "unknown";
  }

  function color(index) {
    return palette[index % palette.length];
  }

  function pickNumber() {
    for (let index = 0; index < arguments.length; index += 1) {
      const parsed = num(arguments[index]);
      if (parsed !== null) {
        return parsed;
      }
    }
    return null;
  }

  function sumKnown(values) {
    let total = 0;
    let found = false;
    values.forEach((value) => {
      const parsed = num(value);
      if (parsed !== null) {
        total += parsed;
        found = true;
      }
    });
    return found ? total : null;
  }

  function fmtCount(value) {
    const parsed = num(value);
    return parsed === null ? "n/a" : String(Math.round(parsed));
  }

  function fmtR(value) {
    const parsed = num(value);
    if (parsed === null) {
      return "n/a";
    }
    return `${parsed > 0 ? "+" : ""}${parsed.toFixed(1)}R`;
  }

  function fmtPct(value) {
    const parsed = num(value);
    return parsed === null ? "n/a" : `${parsed.toFixed(1)}%`;
  }

  function fmtMoney(value) {
    const parsed = num(value);
    if (parsed === null) {
      return "n/a";
    }
    return `EUR ${parsed > 0 ? "+" : ""}${parsed.toFixed(2)}`;
  }

  function fmtDate(value) {
    if (!value) {
      return "";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return String(value);
    }
    return parsed.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function fmtShortDate(value) {
    if (!value) {
      return "";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return String(value);
    }
    return parsed.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function decisionPillStyle(decision) {
    if (decision === "BUY") {
      return "background:rgba(0,255,170,0.12);color:var(--green);border:1px solid rgba(0,255,170,0.2)";
    }
    if (decision === "SELL") {
      return "background:rgba(255,77,106,0.12);color:var(--red);border:1px solid rgba(255,77,106,0.2)";
    }
    return "background:rgba(77,159,255,0.12);color:var(--blue);border:1px solid rgba(77,159,255,0.2)";
  }

  function pnlClass(value) {
    const parsed = num(value);
    if (parsed === null) {
      return "";
    }
    if (parsed > 0) {
      return "positive";
    }
    if (parsed < 0) {
      return "negative";
    }
    return "";
  }

  function grossPnlR(model) {
    return pickNumber(model.cumulative_realized_pnl_r);
  }

  function netPnlR(model) {
    return pickNumber(model.net_pnl_r, model.cumulative_realized_pnl_r);
  }

  function grossPnlEur(model) {
    return pickNumber(model.gross_pnl_eur, model.cumulative_realized_pnl_eur);
  }

  function netPnlEur(model) {
    return pickNumber(model.net_pnl_eur);
  }

  function totalTrades(model) {
    return pickNumber(model.total_trades, model.actionable_total);
  }

  function evaluations(model) {
    return pickNumber(model.evaluations_total, model.total_trades);
  }

  function openTrades(model) {
    const explicit = pickNumber(model.open_trades);
    if (explicit !== null) {
      return explicit;
    }
    const actionables = pickNumber(model.total_trades, model.actionable_total);
    const closed = pickNumber(model.closed_total);
    if (actionables !== null && closed !== null) {
      return Math.max(actionables - closed, 0);
    }
    return null;
  }

  function maxDrawdownR(model) {
    const explicit = pickNumber(model.max_drawdown_r);
    if (explicit !== null) {
      return explicit;
    }
    const curve = Array.isArray(model.equity_curve) ? model.equity_curve : [];
    const values = curve
      .map((point) => num(point.equity_r))
      .filter((value) => value !== null);
    if (!values.length) {
      return null;
    }
    return Math.min.apply(null, values);
  }

  function totalCosts(model) {
    return pickNumber(model.total_costs_eur);
  }

  function costPerTrade(model) {
    const explicit = pickNumber(model.cost_per_trade_eur);
    if (explicit !== null) {
      return explicit;
    }
    const costs = totalCosts(model);
    const trades = totalTrades(model);
    if (costs !== null && trades !== null && trades > 0) {
      return costs / trades;
    }
    return null;
  }

  function costsAsPctOfGross(model) {
    const explicit = pickNumber(model.costs_as_pct_of_gross);
    if (explicit !== null) {
      return explicit;
    }
    const costs = totalCosts(model);
    const gross = grossPnlEur(model);
    if (costs !== null && gross !== null && gross !== 0) {
      return (costs / Math.abs(gross)) * 100;
    }
    return null;
  }

  function costComponents(model) {
    return [
      { label: "Spread", value: pickNumber(model.spread_cost_eur) },
      { label: "Commission", value: pickNumber(model.commission_cost_eur) },
      { label: "Swap", value: pickNumber(model.swap_cost_eur) },
      { label: "Slippage", value: pickNumber(model.slippage_cost_eur) },
    ].filter((item) => item.value !== null);
  }

  function buildOverview(data) {
    const overview = data.overview || {};
    const items = data.leaderboard || [];
    return {
      modelCount: pickNumber(overview.model_count, items.length) || 0,
      entryCount: pickNumber(
        overview.tournament_entry_count,
        sumKnown(items.map((item) => evaluations(item)))
      ) || 0,
      settlementCount: pickNumber(
        overview.settlement_count,
        sumKnown(items.map((item) => item.closed_total))
      ) || 0,
      reflectionCount: pickNumber(overview.reflection_snapshot_count) || 0,
      openTrades: pickNumber(
        overview.open_trades,
        sumKnown(items.map((item) => openTrades(item)))
      ),
      totalGrossPnlEur: pickNumber(
        overview.total_gross_pnl_eur,
        sumKnown(items.map((item) => grossPnlEur(item)))
      ),
      totalNetPnlEur: pickNumber(
        overview.total_net_pnl_eur,
        sumKnown(items.map((item) => netPnlEur(item)))
      ),
      totalCostsEur: pickNumber(
        overview.total_costs_eur,
        sumKnown(items.map((item) => totalCosts(item)))
      ),
      bestWinrate: pickNumber(
        overview.best_winrate,
        items.reduce((best, item) => {
          const winRate = num(item.win_rate_percent);
          if (winRate === null) {
            return best;
          }
          return best === null ? winRate : Math.max(best, winRate);
        }, null)
      ),
    };
  }

  function renderTicker(data) {
    const element = document.getElementById("ticker-bar");
    const overview = buildOverview(data);
    const items = [
      { label: "Models", value: fmtCount(overview.modelCount) },
      { label: "Entries", value: fmtCount(overview.entryCount) },
      { label: "Settled", value: fmtCount(overview.settlementCount) },
      { label: "Open", value: fmtCount(overview.openTrades) },
      { label: "Gross PnL", value: fmtMoney(overview.totalGrossPnlEur), cls: pnlClass(overview.totalGrossPnlEur) },
      { label: "Net PnL", value: fmtMoney(overview.totalNetPnlEur), cls: pnlClass(overview.totalNetPnlEur) },
      { label: "Total Costs", value: fmtMoney(overview.totalCostsEur), cls: pnlClass(-Math.abs(pickNumber(overview.totalCostsEur, 0))) },
      { label: "Best WR", value: fmtPct(overview.bestWinrate) },
      { label: "Reflections", value: fmtCount(overview.reflectionCount) },
    ];

    element.innerHTML = items
      .map(
        (item) =>
          `<div class="ticker-item"><span class="ticker-label">${esc(item.label)}</span><span class="ticker-value ${item.cls || ""}">${esc(item.value)}</span></div>`
      )
      .join("");
  }

  function renderStatus(data, label) {
    document.getElementById("data-source").textContent = label;
    document.getElementById("generated-at").textContent = data.generated_at
      ? `Updated ${fmtDate(data.generated_at)}`
      : "";
  }

  function renderLiveStatus(data) {
    const element = document.getElementById("live-status");
    const status = data.live_status || {};
    const state = status.state || "idle";
    const stateClass =
      state === "has_data"
        ? "live-status-good"
        : state === "waiting_for_h4_close"
          ? "live-status-wait"
          : state === "running"
            ? "live-status-running"
            : "live-status-idle";

    const nextClose = status.next_h4_close_utc ? fmtDate(status.next_h4_close_utc) : "n/a";
    const lastTrigger = status.last_trigger_time ? fmtDate(status.last_trigger_time) : "n/a";

    element.innerHTML = `
      <div class="live-status-shell ${stateClass}">
        <div class="live-status-copy">
          <div class="live-status-headline">${esc(status.headline || "Geen live status beschikbaar.")}</div>
          <div class="live-status-detail">${esc(status.detail || "Het dashboard wacht op een nieuwe tournament-run.")}</div>
        </div>
        <div class="live-status-meta">
          <div class="live-status-item"><span class="live-status-label">Last Check</span><span class="live-status-value">${esc(lastTrigger)}</span></div>
          <div class="live-status-item"><span class="live-status-label">Next H4 Close</span><span class="live-status-value">${esc(nextClose)}</span></div>
        </div>
      </div>
    `;
  }

  function renderLeaderboard(data) {
    const element = document.getElementById("leaderboard");
    const items = data.leaderboard || [];
    if (!items.length) {
      element.innerHTML = '<div class="empty-state">No leaderboard data yet.</div>';
      return;
    }

    element.innerHTML = items
      .map((item, index) => {
        const rank = item.leaderboard_rank || index + 1;
        const rankClass = rank === 1 ? "gold" : rank === 2 ? "silver" : rank === 3 ? "bronze" : "default";
        const statusClass =
          item.latest_outcome_status === "take_profit_hit"
            ? "pill-win"
            : item.latest_outcome_status === "stop_loss_hit"
              ? "pill-loss"
              : "pill-pending";

        return `
          <div class="lb-row rank-${rank}">
            <div class="lb-rank ${rankClass}">#${rank}</div>
            <div class="lb-info">
              <div class="lb-name">${esc(modelName(item.model_id, item.display_name))}</div>
              <div class="lb-subtitle">
                <span class="lb-pill ${statusClass}">${esc(item.latest_outcome_status || "pending")}</span>
                <span>Conf: ${esc(fmtCount(item.average_confidence_score))}</span>
                <span>Agreement: ${esc(fmtPct(item.baseline_agreement_rate_percent))}</span>
                <span>Invalid: ${esc(fmtCount(item.invalid_output_count))}</span>
              </div>
            </div>
            <div class="lb-stats">
              <div class="lb-stat"><div class="lb-stat-value ${pnlClass(grossPnlR(item))}">${esc(fmtR(grossPnlR(item)))}</div><div class="lb-stat-label">Gross R</div></div>
              <div class="lb-stat"><div class="lb-stat-value ${pnlClass(netPnlR(item))}">${esc(fmtR(netPnlR(item)))}</div><div class="lb-stat-label">Net R</div></div>
              <div class="lb-stat"><div class="lb-stat-value">${esc(fmtPct(item.win_rate_percent))}</div><div class="lb-stat-label">Win Rate</div></div>
              <div class="lb-stat"><div class="lb-stat-value ${pnlClass(maxDrawdownR(item))}">${esc(fmtR(maxDrawdownR(item)))}</div><div class="lb-stat-label">Max DD</div></div>
              <div class="lb-stat"><div class="lb-stat-value">${esc(fmtCount(totalTrades(item)))}</div><div class="lb-stat-label">Trades</div></div>
              <div class="lb-stat"><div class="lb-stat-value">${esc(fmtCount(openTrades(item)))}</div><div class="lb-stat-label">Open</div></div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function renderEquityLegend(data) {
    const element = document.getElementById("equity-legend");
    const items = data.leaderboard || [];
    element.innerHTML = items
      .map(
        (item, index) =>
          `<span class="legend-chip"><span class="legend-dot" style="background:${color(index)}"></span>${esc(modelName(item.model_id, item.display_name))}</span>`
      )
      .join("");
  }

  function renderEquityChart(data) {
    const host = document.getElementById("equity-chart");
    const items = data.leaderboard || [];
    if (!items.length) {
      host.innerHTML = '<div class="empty-state">No equity data.</div>';
      return;
    }

    const allPoints = items.flatMap((item) => item.equity_curve || []);
    if (!allPoints.length) {
      host.innerHTML = '<div class="empty-state">No curve points.</div>';
      return;
    }

    const width = 880;
    const height = 320;
    const padding = { top: 28, right: 24, bottom: 36, left: 52 };
    const minY = Math.min(0, ...allPoints.map((point) => pickNumber(point.equity_r, 0)));
    const maxY = Math.max(0, ...allPoints.map((point) => pickNumber(point.equity_r, 0)));
    const rangeY = Math.max(1, maxY - minY);
    const xCount = Math.max(...items.map((item) => (item.equity_curve || []).length), 1);

    const mapX = (index, count) => {
      const span = width - padding.left - padding.right;
      return count <= 1 ? padding.left + span / 2 : padding.left + (span * index) / (count - 1);
    };
    const mapY = (value) => padding.top + ((maxY - value) / rangeY) * (height - padding.top - padding.bottom);

    const gridValues = [maxY, (maxY + minY) / 2, minY];
    const gridMarkup = gridValues
      .map((value) => {
        const y = mapY(value);
        return `<line class="axis-grid" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}"/>
          <text class="axis-tick" x="${padding.left - 8}" y="${y + 4}" text-anchor="end">${esc(fmtR(value))}</text>`;
      })
      .join("");

    const xTicks = Array.from({ length: xCount }, (_, index) => {
      const x = mapX(index, xCount);
      return `<text class="axis-tick" x="${x}" y="${height - 8}" text-anchor="middle">T${index + 1}</text>`;
    }).join("");

    const zeroY = mapY(0);
    const zeroLine = `<line x1="${padding.left}" y1="${zeroY}" x2="${width - padding.right}" y2="${zeroY}" stroke="rgba(255,255,255,0.15)" stroke-width="1" stroke-dasharray="4,4"/>`;

    const series = items
      .map((item, index) => {
        const points = item.equity_curve || [];
        const stroke = color(index);
        const polyline = points
          .map((point, pointIndex) => `${mapX(pointIndex, points.length)},${mapY(pickNumber(point.equity_r, 0))}`)
          .join(" ");
        const areaStart = `${mapX(0, points.length)},${zeroY}`;
        const areaEnd = `${mapX(points.length - 1, points.length)},${zeroY}`;
        const area = `<polygon fill="${stroke}" opacity="0.06" points="${areaStart} ${polyline} ${areaEnd}"/>`;
        const markers = points
          .map((point, pointIndex) => {
            const x = mapX(pointIndex, points.length);
            const y = mapY(pickNumber(point.equity_r, 0));
            return `<circle cx="${x}" cy="${y}" r="4" fill="${stroke}" stroke="var(--bg)" stroke-width="2"/>`;
          })
          .join("");
        return `<g style="color:${stroke}">${area}<polyline class="line-glow" fill="none" stroke="${stroke}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${polyline}"/>${markers}</g>`;
      })
      .join("");

    host.innerHTML = `<svg class="chart-shell" viewBox="0 0 ${width} ${height}" role="img" aria-label="Equity curves">${gridMarkup}${zeroLine}${xTicks}<text class="axis-label" x="${padding.left}" y="16">Realized PnL (R)</text>${series}</svg>`;
  }

  function renderCostBreakdown(data) {
    const element = document.getElementById("cost-breakdown");
    const items = data.leaderboard || [];
    if (!items.length) {
      element.innerHTML = '<div class="empty-state">No cost data.</div>';
      return;
    }

    element.innerHTML = items
      .map((item, index) => {
        const components = costComponents(item);
        const maxBar = Math.max(1, ...components.map((component) => component.value));
        const netValue = netPnlEur(item);
        const currentEquity = pickNumber(item.current_equity_eur);
        const secondarySummaryLabel = netValue !== null ? "Net PnL" : "Current Equity";
        const secondarySummaryValue = netValue !== null ? fmtMoney(netValue) : fmtMoney(currentEquity);

        return `
          <div class="cost-row">
            <div>
              <div class="cost-model" style="color:${color(index)}">${esc(modelName(item.model_id, item.display_name))}</div>
              ${
                components.length
                  ? `<div class="cost-bars">
                    ${components
                      .map(
                        (component) => `
                          <div class="cost-bar-row">
                            <span class="cost-bar-label">${esc(component.label)}</span>
                            <div class="cost-bar-track"><div class="cost-bar-fill" style="width:${((component.value / maxBar) * 100).toFixed(1)}%"></div></div>
                            <span class="cost-bar-value">${esc(fmtMoney(component.value))}</span>
                          </div>
                        `
                      )
                      .join("")}
                  </div>`
                  : '<div class="cost-bar-empty">Detailed cost components are not present in the current view model.</div>'
              }
            </div>
            <div class="cost-summary">
              <div class="cost-summary-item"><div class="cost-summary-label">Gross PnL</div><div class="cost-summary-value ${pnlClass(grossPnlEur(item))}">${esc(fmtMoney(grossPnlEur(item)))}</div></div>
              <div class="cost-summary-item"><div class="cost-summary-label">${esc(secondarySummaryLabel)}</div><div class="cost-summary-value ${pnlClass(netValue !== null ? netValue : currentEquity)}">${esc(secondarySummaryValue)}</div></div>
              <div class="cost-summary-item"><div class="cost-summary-label">Cost / Trade</div><div class="cost-summary-value">${esc(fmtMoney(costPerTrade(item)))}</div></div>
              <div class="cost-summary-item"><div class="cost-summary-label">Cost % Gross</div><div class="cost-summary-value cost-warn">${esc(fmtPct(costsAsPctOfGross(item)))}</div></div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function renderDiscipline(data) {
    const element = document.getElementById("discipline-grid");
    const items = data.leaderboard || [];
    if (!items.length) {
      element.innerHTML = '<div class="empty-state">No discipline data.</div>';
      return;
    }

    const hasDecisionCounts = items.some(
      (item) =>
        item.buy_count !== undefined ||
        item.sell_count !== undefined ||
        item.wait_count !== undefined ||
        item.nogo_count !== undefined
    );

    const columns = hasDecisionCounts
      ? [
          { label: "BUY", getValue: (item) => fmtCount(item.buy_count) },
          { label: "SELL", getValue: (item) => fmtCount(item.sell_count) },
          { label: "WAIT", getValue: (item) => fmtCount(item.wait_count) },
          { label: "NO-GO", getValue: (item) => fmtCount(item.nogo_count) },
          { label: "Invalid", getValue: (item) => fmtCount(item.invalid_output_count), danger: (item) => pickNumber(item.invalid_output_count, 0) > 3 },
          { label: "Agree %", getValue: (item) => fmtPct(item.baseline_agreement_rate_percent) },
          { label: "Avg Conf", getValue: (item) => fmtCount(item.average_confidence_score) },
        ]
      : [
          { label: "Evals", getValue: (item) => fmtCount(evaluations(item)) },
          { label: "Action", getValue: (item) => fmtCount(totalTrades(item)) },
          { label: "Closed", getValue: (item) => fmtCount(item.closed_total) },
          { label: "Wins", getValue: (item) => fmtCount(item.wins_total) },
          { label: "Losses", getValue: (item) => fmtCount(item.losses_total) },
          { label: "Invalid", getValue: (item) => fmtCount(item.invalid_output_count), danger: (item) => pickNumber(item.invalid_output_count, 0) > 3 },
          { label: "Agree %", getValue: (item) => fmtPct(item.baseline_agreement_rate_percent) },
          { label: "Avg Conf", getValue: (item) => fmtCount(item.average_confidence_score) },
        ];

    const header = `
      <div class="disc-row disc-header">
        <div class="disc-model"></div>
        ${columns.map((column) => `<div class="disc-cell"><div class="disc-cell-label">${esc(column.label)}</div></div>`).join("")}
      </div>
    `;

    const rows = items
      .map(
        (item, index) => `
          <div class="disc-row">
            <div class="disc-model" style="color:${color(index)}">${esc(modelName(item.model_id, item.display_name))}</div>
            ${columns
              .map((column) => {
                const danger = column.danger && column.danger(item);
                return `<div class="disc-cell"><div class="disc-cell-value ${danger ? "danger" : ""}">${esc(column.getValue(item))}</div></div>`;
              })
              .join("")}
          </div>
        `
      )
      .join("");

    element.innerHTML = header + rows;
  }

  function renderPerfBars(data) {
    const element = document.getElementById("performance-bars");
    const items = data.leaderboard || [];
    if (!items.length) {
      element.innerHTML = '<div class="empty-state">No performance data.</div>';
      return;
    }

    const maxMagnitude = Math.max(1, ...items.map((item) => Math.abs(pickNumber(netPnlR(item), 0))));

    element.innerHTML = items
      .map((item, index) => {
        const pnl = pickNumber(netPnlR(item), 0);
        const width = Math.max(8, (Math.abs(pnl) / maxMagnitude) * 100);
        return `
          <div class="perf-row">
            <div class="perf-topline">
              <span class="perf-name" style="color:${color(index)}">${esc(modelName(item.model_id, item.display_name))}</span>
              <span class="perf-pnl ${pnlClass(pnl)}">${esc(fmtR(pnl))} net</span>
            </div>
            <div class="perf-track"><div class="perf-fill" style="width:${width}%;background:linear-gradient(90deg,${color(index)},${color(index)}66)"></div></div>
            <div class="perf-meta">
              <div class="perf-meta-item"><span class="perf-meta-label">Win Rate</span><span class="perf-meta-value">${esc(fmtPct(item.win_rate_percent))}</span></div>
              <div class="perf-meta-item"><span class="perf-meta-label">Drawdown</span><span class="perf-meta-value danger">${esc(fmtR(maxDrawdownR(item)))}</span></div>
              <div class="perf-meta-item"><span class="perf-meta-label">Costs</span><span class="perf-meta-value cost-warn">${esc(fmtMoney(totalCosts(item)))}</span></div>
              <div class="perf-meta-item"><span class="perf-meta-label">Trades</span><span class="perf-meta-value">${esc(fmtCount(totalTrades(item)))}</span></div>
              <div class="perf-meta-item"><span class="perf-meta-label">Open</span><span class="perf-meta-value">${esc(fmtCount(openTrades(item)))}</span></div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function renderPairs(data) {
    const element = document.getElementById("pair-performance");
    const items = data.pair_performance || [];
    if (!items.length) {
      element.innerHTML = '<div class="empty-state">No pair data yet. Pair breakdown will appear after the view model exposes market-level detail.</div>';
      return;
    }

    element.innerHTML = items
      .map((item) => {
        const winRate = item.trades > 0 ? ((item.wins / item.trades) * 100).toFixed(0) : "0";
        return `
          <div class="pair-card">
            <div class="pair-name">${esc(item.pair)}</div>
            <div class="pair-stats">
              <div><div class="pair-stat-label">Net PnL</div><div class="pair-stat-value ${pnlClass(item.net_pnl_r)}">${esc(fmtR(item.net_pnl_r))}</div></div>
              <div><div class="pair-stat-label">Win Rate</div><div class="pair-stat-value">${esc(`${winRate}%`)}</div></div>
              <div><div class="pair-stat-label">Trades</div><div class="pair-stat-value">${esc(fmtCount(item.trades))}</div></div>
              <div><div class="pair-stat-label">Best Model</div><div class="pair-stat-value pair-best">${esc(item.best_model)}</div></div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function renderDecisions(data) {
    const element = document.getElementById("recent-decisions");
    const items = data.recent_decisions || [];
    if (!items.length) {
      element.innerHTML = '<div class="empty-state">No recent decisions.</div>';
      return;
    }

    element.innerHTML = items
      .map((item) => {
        const aligned = item.primary_decision ? item.decision === item.primary_decision : null;
        const pillStyle = decisionPillStyle(item.decision);
        const reasons = (item.reason_codes || []).map((reason) => `<span class="reason-tag">${esc(reason)}</span>`).join("");

        return `
          <div class="dec-card">
            <div class="dec-top">
              <span class="dec-model">${esc(modelName(item.model_id, item.display_name))}</span>
              <span class="dec-pill" style="${pillStyle}">${esc(item.decision || "WAIT")}</span>
            </div>
            <div class="dec-summary">${esc(item.summary || "No summary.")}</div>
            <div class="dec-meta">
              <div class="dec-meta-item"><span class="dec-meta-label">Confidence</span><span class="dec-meta-value">${esc(fmtCount(item.confidence_score))}</span></div>
              <div class="dec-meta-item"><span class="dec-meta-label">Baseline</span><span class="dec-meta-value ${aligned === false ? "danger" : aligned === true ? "good" : ""}">${esc(aligned === null ? "n/a" : aligned ? "Aligned" : "Diverged")}</span></div>
              <div class="dec-meta-item"><span class="dec-meta-label">Time</span><span class="dec-meta-value">${esc(fmtDate(item.recorded_at))}</span></div>
            </div>
            ${reasons ? `<div class="dec-reasons">${reasons}</div>` : ""}
          </div>
        `;
      })
      .join("");
  }

  function renderCandleBriefings(data) {
    const element = document.getElementById("candle-briefings");
    const items = data.candle_briefings || [];
    if (!items.length) {
      element.innerHTML = '<div class="empty-state">Nog geen 4H candle-briefings beschikbaar.</div>';
      return;
    }

    const tabs = items
      .map((item, index) => {
        const active = index === 0 ? "is-active" : "";
        const label = `${item.pair || "PAIR"} · ${fmtShortDate(item.recorded_at)}`;
        return `
          <button class="candle-tab ${active}" type="button" data-candle-tab="${index}">
            <span class="candle-tab-title">${esc(label)}</span>
            <span class="candle-tab-meta">${esc(`Primary ${item.primary_decision || "n/a"} · trades ${fmtCount(item.trade_count)}`)}</span>
          </button>
        `;
      })
      .join("");

    const panels = items
      .map((item, index) => {
        const active = index === 0 ? "is-active" : "";
        const models = (item.models || [])
          .map((model) => {
            const tradeState = model.policy_enforced
              ? "geen trade"
              : model.trade_opened
                ? "trade gemaakt"
                : "geen trade";
            const summary = model.policy_enforced
              ? `Het model wilde ${model.model_decision || model.decision}, maar de Set & Forget hard gate blokkeerde die trade.`
              : model.model_summary || model.summary || "Geen toelichting.";
            const finalSummary = model.policy_enforced
              ? model.model_summary || model.summary || "Geen extra toelichting."
              : model.summary && model.summary !== model.model_summary
                ? model.summary
                : "";
            const reasons = (model.model_reason_codes || model.reason_codes || [])
              .map((reason) => `<span class="reason-tag">${esc(reason)}</span>`)
              .join("");

            return `
              <details class="candle-model-card">
                <summary class="candle-model-summary">
                  <div class="candle-model-head">
                    <span class="candle-model-name">${esc(modelName(model.model_id, model.display_name))}</span>
                    <span class="dec-pill" style="${decisionPillStyle(model.policy_enforced ? "WAIT" : model.decision)}">${esc(tradeState)}</span>
                  </div>
                  <div class="candle-model-sub">
                    <span>${esc(`Model ${model.model_decision || model.decision}`)}</span>
                    <span>${esc(`Final ${model.decision || "WAIT"}`)}</span>
                    <span>${esc(`Confidence ${fmtCount(model.model_confidence_score)}`)}</span>
                  </div>
                </summary>
                <div class="candle-model-body">
                  <p class="candle-model-copy">${esc(summary)}</p>
                  ${finalSummary ? `<p class="candle-model-copy candle-model-copy-muted">${esc(finalSummary)}</p>` : ""}
                  <div class="candle-model-meta">
                    <div class="dec-meta-item"><span class="dec-meta-label">Time</span><span class="dec-meta-value">${esc(fmtDate(model.recorded_at))}</span></div>
                    <div class="dec-meta-item"><span class="dec-meta-label">Hard Gate</span><span class="dec-meta-value ${model.policy_enforced ? "danger" : "good"}">${esc(model.policy_enforced ? "Blocked" : "Clear")}</span></div>
                  </div>
                  ${reasons ? `<div class="dec-reasons">${reasons}</div>` : ""}
                </div>
              </details>
            `;
          })
          .join("");

        return `
          <section class="candle-panel ${active}" data-candle-panel="${index}">
            <div class="candle-panel-top">
              <div>
                <div class="candle-panel-title">${esc(`${item.pair || "PAIR"} · ${item.execution_timeframe || "4H"}`)}</div>
                <div class="candle-panel-subtitle">${esc(`Closed ${fmtDate(item.recorded_at)} · ${item.model_count || 0} models`)}</div>
              </div>
              <div class="candle-panel-stats">
                <span class="candle-panel-chip">${esc(`Primary ${item.primary_decision || "n/a"}`)}</span>
                <span class="candle-panel-chip">${esc(`Trades ${fmtCount(item.trade_count)}`)}</span>
                <span class="candle-panel-chip">${esc(`Blocked ${fmtCount(item.blocked_trade_count)}`)}</span>
              </div>
            </div>
            <div class="candle-model-list">${models}</div>
          </section>
        `;
      })
      .join("");

    element.innerHTML = `
      <div class="candle-tabs">${tabs}</div>
      <div class="candle-panels">${panels}</div>
    `;

    const buttons = element.querySelectorAll("[data-candle-tab]");
    const panelsEls = element.querySelectorAll("[data-candle-panel]");
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.getAttribute("data-candle-tab");
        buttons.forEach((item) => item.classList.toggle("is-active", item === button));
        panelsEls.forEach((panel) => panel.classList.toggle("is-active", panel.getAttribute("data-candle-panel") === target));
      });
    });
  }

  async function loadViewModel() {
    const params = new URLSearchParams(window.location.search);
    const path = params.get("data") || "./openclaw_tournament_dashboard_view_model.json";
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return {
        data: await response.json(),
        label: `Live data | ${path}`,
      };
    } catch (error) {
      return {
        data: fallbackViewModel,
        label: `Demo data | ${path} unavailable`,
      };
    }
  }

  async function main() {
    const { data, label } = await loadViewModel();
    renderStatus(data, label);
    renderLiveStatus(data);
    renderTicker(data);
    renderLeaderboard(data);
    renderEquityLegend(data);
    renderEquityChart(data);
    renderCostBreakdown(data);
    renderDiscipline(data);
    renderPerfBars(data);
    renderPairs(data);
    renderDecisions(data);
    renderCandleBriefings(data);
  }

  main();
})();
