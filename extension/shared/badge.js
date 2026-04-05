(() => {
  const COLORS = {
    safe: "#16a34a",
    suspicious: "#d97706",
    likely_scam: "#dc2626",
    loading: "#6b7280",
    error: "#9ca3af",
  };

  const VERDICT_TEXT = {
    safe: "Looks Legit",
    suspicious: "Proceed with Caution",
    likely_scam: "Likely Scam",
  };

  const VERDICT_ICON = { safe: "✓", suspicious: "⚠", likely_scam: "✕" };

  const WALKABILITY_ICON = { high: "🟢", medium: "🟡", low: "🔴", unknown: "⚪" };

  // ── Stylesheet ───────────────────────────────────────────────────
  const style = document.createElement("style");
  style.textContent = `
    #rs-panel {
      position: fixed;
      top: 80px;
      right: 0;
      width: 256px;
      border-radius: 12px 0 0 12px;
      box-shadow: -3px 2px 14px rgba(0,0,0,.22);
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 13px;
      z-index: 2147483647;
      overflow: hidden;
    }
    #rs-header {
      padding: 10px 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      user-select: none;
      transition: background .3s;
    }
    .rs-logo {
      background: rgba(255,255,255,.25);
      border-radius: 5px;
      padding: 2px 6px;
      font-weight: 700;
      font-size: 11px;
      letter-spacing: .5px;
      color: #fff;
      flex-shrink: 0;
    }
    .rs-score {
      font-size: 22px;
      font-weight: 800;
      color: #fff;
      line-height: 1;
      flex-shrink: 0;
    }
    .rs-verdict {
      font-size: 12px;
      color: rgba(255,255,255,.9);
      flex: 1;
      line-height: 1.3;
    }
    .rs-chevron {
      color: rgba(255,255,255,.7);
      font-size: 11px;
      flex-shrink: 0;
    }
    #rs-body {
      background: #fff;
      max-height: 420px;
      overflow-y: auto;
      transition: max-height .2s ease;
    }
    #rs-panel.rs-collapsed #rs-body { max-height: 0; }

    /* Section headings */
    .rs-section-head {
      padding: 8px 12px 3px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: .6px;
      color: #9ca3af;
      text-transform: uppercase;
    }

    /* Score bars */
    .rs-bar-row {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 3px 12px;
    }
    .rs-bar-label {
      font-size: 11px;
      color: #6b7280;
      width: 80px;
      flex-shrink: 0;
    }
    .rs-bar-track {
      flex: 1;
      height: 6px;
      background: #f3f4f6;
      border-radius: 9999px;
      overflow: hidden;
    }
    .rs-bar-fill {
      height: 100%;
      border-radius: 9999px;
      transition: width .4s ease;
    }
    .rs-bar-val {
      font-size: 11px;
      color: #374151;
      width: 24px;
      text-align: right;
      flex-shrink: 0;
    }

    /* Red flags */
    .rs-flag-item {
      display: flex;
      gap: 8px;
      align-items: baseline;
      padding: 5px 12px;
      font-size: 12px;
      color: #1f2937;
      line-height: 1.4;
      border-bottom: 1px solid #f9fafb;
    }
    .rs-flag-dot { color: #dc2626; flex-shrink: 0; font-size: 9px; }

    /* Accessibility signals */
    .rs-signal-item {
      display: flex;
      align-items: baseline;
      gap: 6px;
      padding: 4px 12px;
      font-size: 12px;
      color: #15803d;
      line-height: 1.4;
    }

    /* Neighborhood grid */
    .rs-hood-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      padding: 6px 12px 10px;
    }
    .rs-hood-cell {
      background: #f9fafb;
      border-radius: 8px;
      padding: 6px 8px;
      font-size: 11px;
      color: #374151;
      line-height: 1.4;
    }
    .rs-hood-cell strong {
      display: block;
      font-size: 15px;
      font-weight: 700;
      color: #111827;
    }

    /* Market price note */
    .rs-market-note {
      margin: 0 12px 10px;
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 8px;
      padding: 7px 10px;
      font-size: 12px;
      color: #92400e;
      line-height: 1.5;
    }

    /* No flags / error */
    .rs-none { padding: 10px 12px; color: #16a34a; font-size: 13px; }
    .rs-error-msg { padding: 10px 12px; color: #6b7280; font-size: 12px; }

    /* Divider */
    .rs-divider { height: 1px; background: #f3f4f6; margin: 4px 0; }

    /* ── Small screens: bottom bar ── */
    @media (max-width: 600px) {
      #rs-panel {
        top: auto;
        bottom: 0;
        left: 0;
        right: 0;
        width: 100%;
        border-radius: 12px 12px 0 0;
        box-shadow: 0 -3px 14px rgba(0,0,0,.18);
      }
      .rs-score { font-size: 18px; }
      #rs-body { max-height: 55vh; }
      #rs-panel.rs-collapsed #rs-body { max-height: 0; }
    }
  `;
  document.head.appendChild(style);

  // ── Helpers ──────────────────────────────────────────────────────
  function el(tag, className, html) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function barColor(score) {
    if (score >= 66) return "#dc2626";
    if (score >= 40) return "#d97706";
    return "#16a34a";
  }

  function sectionHead(text) {
    return el("div", "rs-section-head", text);
  }

  function scoreBar(label, score) {
    const row = el("div", "rs-bar-row", "");
    const lbl = el("div", "rs-bar-label", label);
    const track = el("div", "rs-bar-track", "");
    const fill = el("div", "rs-bar-fill", "");
    fill.style.cssText = `width:${score}%;background:${barColor(score)}`;
    track.appendChild(fill);
    const val = el("div", "rs-bar-val", String(score));
    row.append(lbl, track, val);
    return row;
  }

  // ── Badge object ─────────────────────────────────────────────────
  const RentSentryBadge = {
    _panel: null,
    _header: null,
    _scoreEl: null,
    _verdictEl: null,
    _chevron: null,
    _body: null,
    _collapsed: false,

    mount(_anchorEl) {
      if (document.getElementById("rs-panel")) return;

      this._panel = document.createElement("div");
      this._panel.id = "rs-panel";

      this._header = document.createElement("div");
      this._header.id = "rs-header";
      this._header.style.background = COLORS.loading;

      const logo = el("span", "rs-logo", "RS");
      this._scoreEl = el("span", "rs-score", "…");
      this._verdictEl = el("span", "rs-verdict", "Analyzing");
      this._chevron = el("span", "rs-chevron", "▴");

      this._header.append(logo, this._scoreEl, this._verdictEl, this._chevron);

      this._body = document.createElement("div");
      this._body.id = "rs-body";

      this._header.addEventListener("click", () => {
        this._collapsed = !this._collapsed;
        this._panel.classList.toggle("rs-collapsed", this._collapsed);
        this._chevron.textContent = this._collapsed ? "▾" : "▴";
      });

      this._panel.append(this._header, this._body);
      document.body.appendChild(this._panel);
    },

    showResult(data) {
      if (!this._panel) return;
      const {
        trust_score, verdict, red_flags = [],
        llm_score, price_score,
        accessibility_signals = [],
        neighborhood_note, neighborhood_info,
        market_price_score,
        listing_price_usd,
        meta,
      } = data;

      const color = COLORS[verdict] || COLORS.loading;
      const label = VERDICT_TEXT[verdict] || verdict;
      const icon = VERDICT_ICON[verdict] || "";

      this._header.style.background = color;
      this._scoreEl.textContent = trust_score;
      this._verdictEl.innerHTML =
        `<strong>${icon} ${label}</strong><br><span style="opacity:.75;font-size:11px">RentSentry</span>`;

      this._body.innerHTML = "";

      // ── 1. Score breakdown ──────────────────────────────────────
      this._body.appendChild(sectionHead("Score Breakdown"));
      this._body.appendChild(scoreBar("Fraud signals", llm_score));
      this._body.appendChild(scoreBar("Price risk", price_score));
      this._body.appendChild(el("div", "rs-divider", ""));

      // ── 2. Red flags ────────────────────────────────────────────
      if (red_flags.length > 0) {
        this._body.appendChild(
          sectionHead(`${red_flags.length} Red Flag${red_flags.length !== 1 ? "s" : ""}`)
        );
        red_flags.forEach((flag) => {
          const item = el("div", "rs-flag-item", "");
          item.append(el("span", "rs-flag-dot", "●"), el("span", "", flag));
          this._body.appendChild(item);
        });
        this._body.appendChild(el("div", "rs-divider", ""));
      } else {
        this._body.appendChild(el("div", "rs-none", "✓ No red flags detected."));
        this._body.appendChild(el("div", "rs-divider", ""));
      }

      // ── 3. Accessibility signals ────────────────────────────────
      if (accessibility_signals.length > 0) {
        this._body.appendChild(sectionHead("Positive Signals"));
        accessibility_signals.forEach((sig) => {
          this._body.appendChild(el("div", "rs-signal-item", `<span>📍</span><span>${sig}</span>`));
        });
        this._body.appendChild(el("div", "rs-divider", ""));
      }

      // ── 4. Neighborhood card (only when OSM data was actually fetched) ──
      if (neighborhood_info && meta?.neighborhood_detected) {
        const { grocery_stores, transit_stops, restaurants, walkability } = neighborhood_info;
        const hood = meta.neighborhood_detected;
        const hoodName = hood.charAt(0).toUpperCase() + hood.slice(1);
        this._body.appendChild(sectionHead(`Neighborhood · ${hoodName}`));
        const grid = el("div", "rs-hood-grid", "");

        const cells = [
          { label: "Grocery", val: grocery_stores ?? "N/A", icon: "🛒" },
          { label: "Transit stops", val: transit_stops ?? "N/A", icon: "🚌" },
          { label: "Restaurants", val: restaurants ?? "N/A", icon: "🍽" },
          {
            label: "Walkability",
            val: walkability && walkability !== "unknown" ? walkability : "N/A",
            icon: WALKABILITY_ICON[walkability] || "⚪",
            isText: true,
          },
        ];

        cells.forEach(({ label, val, icon, isText }) => {
          const cell = el("div", "rs-hood-cell", "");
          cell.innerHTML = isText
            ? `<strong>${icon} ${val}</strong>${label}`
            : `<strong>${val}</strong>${icon} ${label}`;
          grid.appendChild(cell);
        });

        this._body.appendChild(grid);
        this._body.appendChild(el("div", "rs-divider", ""));
      }

      // ── 5. Market price note (Boston only, same gate as web app) ──
      if (meta?.in_boston_area && neighborhood_note && market_price_score !== null && market_price_score !== undefined) {
        const priceStr = listing_price_usd ? `$${listing_price_usd.toLocaleString()}/mo · ` : "";
        this._body.appendChild(
          el("div", "rs-market-note", `${priceStr}${neighborhood_note}`)
        );
      }
    },

    showError(msg) {
      if (!this._panel) return;
      this._header.style.background = COLORS.error;
      this._scoreEl.textContent = "—";
      this._verdictEl.innerHTML =
        `<strong>Unavailable</strong><br><span style="opacity:.75;font-size:11px">RentSentry</span>`;
      this._body.innerHTML = "";
      this._body.appendChild(el("div", "rs-error-msg", msg || "Could not reach analysis server"));
    },
  };

  window.RentSentryBadge = RentSentryBadge;
})();
