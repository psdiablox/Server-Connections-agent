import { useEffect, useMemo, useState } from "react";
import { api, type Coin, type Heatmap, type Market, type Network, type OrderStats, type Outage, type Tick, type Trade, type WindowSummary } from "../api";
import { fmt, fmtCompact, fmtWindowTime } from "../lib/format";
import { AnalysisChart, type ChartLayers } from "../components/AnalysisChart";
import { TradesTable } from "../components/TradesTable";
import { OrderStatsRail } from "../components/OrderStatsRail";

export function PolyAnalysis({
  network,
  coin,
  window,
  onBack,
  onHome,
}: {
  network: Network;
  coin: Coin;
  window: WindowSummary;
  onBack: (where: "coins" | "windows") => void;
  onHome: () => void;
}) {
  const [market, setMarket] = useState<Market | null>(null);
  const [ticks, setTicks] = useState<Tick[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);
  const [stats, setStats] = useState<OrderStats | null>(null);
  const [outages, setOutages] = useState<Outage[]>([]);
  const [layers, setLayers] = useState<ChartLayers>({
    yes: true, no: true, base: true, strike: true, heatmap: true,
    yesBuy: true, yesSell: true, noBuy: true, noSell: true,
    volume: true,
  });
  const toggle = (k: keyof ChartLayers) => setLayers((v) => ({ ...v, [k]: !v[k] }));
  const [bubblesOpen, setBubblesOpen] = useState(false);
  const setAllBubbles = (on: boolean) =>
    setLayers((v) => ({ ...v, yesBuy: on, yesSell: on, noBuy: on, noSell: on }));
  const bubblesAllOn = layers.yesBuy && layers.yesSell && layers.noBuy && layers.noSell;
  const bubblesAnyOn = layers.yesBuy || layers.yesSell || layers.noBuy || layers.noSell;
  const bubblesOnCount = [layers.yesBuy, layers.yesSell, layers.noBuy, layers.noSell].filter(Boolean).length;

  // Zoom: visible window range as fraction of full [0..1].
  const [zoom, setZoom] = useState<{ a: number; b: number }>({ a: 0, b: 1 });
  const zoomIn = () => setZoom((z) => {
    const mid = (z.a + z.b) / 2;
    const w = (z.b - z.a) / 2;
    return { a: Math.max(0, mid - w / 2), b: Math.min(1, mid + w / 2) };
  });
  const zoomOut = () => setZoom((z) => {
    const mid = (z.a + z.b) / 2;
    const w = Math.min(1, (z.b - z.a) * 2);
    let a = Math.max(0, mid - w / 2);
    let b = Math.min(1, a + w);
    if (b - a < w) a = Math.max(0, b - w);
    return { a, b };
  });
  const zoomReset = () => setZoom({ a: 0, b: 1 });

  useEffect(() => {
    Promise.all([
      api.market(window.id),
      api.ticks(window.id, 5),
      api.trades(window.id, 2000),
      api.heatmap(window.id, 80, 80, "YES").catch(() => null),
      api.orderStats(window.id),
      api.outages(window.id).catch(() => []),
    ])
      .then(([m, t, tr, hm, s, o]) => {
        setMarket(m);
        setTicks(t);
        setTrades(tr);
        setHeatmap(hm);
        setStats(s);
        setOutages(o);
      })
      .catch(console.error);
  }, [window.id]);

  const hero = useMemo(() => {
    if (ticks.length === 0)
      return { open: null, close: null, high: null, low: null, yesPeak: null, yesTrough: null };
    const bases = ticks.map((t) => t.base_price).filter((v): v is number => v != null);
    const yes = ticks.map((t) => t.yes).filter((v): v is number => v != null);
    return {
      open: bases[0] ?? null,
      close: bases[bases.length - 1] ?? null,
      high: bases.length ? Math.max(...bases) : null,
      low: bases.length ? Math.min(...bases) : null,
      yesPeak: yes.length ? Math.max(...yes) : null,
      yesTrough: yes.length ? Math.min(...yes) : null,
    };
  }, [ticks]);

  return (
    <>
      <div className="frame-top">
        <div className="brand"><span className="dot">●</span>TRACE</div>
        <div className="crumb">
          <a onClick={onHome}>NETWORKS</a><span className="sep">/</span>
          <a onClick={() => onBack("coins")} style={{ color: network.color || undefined }}>{network.name.toUpperCase()}</a>
          <span className="sep">/</span>
          <a onClick={() => onBack("windows")} style={{ color: coin.color || undefined }}>{coin.symbol}</a>
          <span className="sep">/</span>
          <span className="cur">{fmtWindowTime(window.starts_at, window.ends_at)} UTC</span>
        </div>
        <div className="ticker">
          <span className={`pw-status ${window.status}`}><span className="dot"></span>{window.status.toUpperCase()}</span>
          {window.resolution && <span className={`pw-res ${window.resolution.toLowerCase()}`} style={{ marginLeft: 6 }}>RESOLVED {window.resolution}</span>}
        </div>
      </div>

      <div className="pa-hero">
        <div className="pa-hero-left">
          <div className="pa-mark">
            <div className="poly-coin-glyph" style={{ borderColor: coin.color || undefined, color: coin.color || undefined, width: 56, height: 56, fontSize: 13 }}>{coin.symbol}</div>
            <div>
              <h1 className="pa-q">{market?.question || `Will ${coin.symbol} close above $${fmt(window.strike, 0)}?`}</h1>
              <div className="pa-meta mono">
                <span className="dim">5 MIN WINDOW</span><span>·</span>
                <span>{fmtWindowTime(window.starts_at, window.ends_at)} UTC</span><span>·</span>
                <span>STRIKE ${fmt(window.strike, 0)}</span>
              </div>
            </div>
          </div>
        </div>
        <div className="pa-hero-stats">
          <Stat label="OPEN" v={hero.open != null ? "$" + fmt(hero.open, 0) : "—"} />
          <Stat label="CLOSE" v={hero.close != null ? "$" + fmt(hero.close, 0) : "—"} dir={hero.close != null && window.strike != null ? (hero.close >= window.strike ? "up" : "down") : ""} />
          <Stat label="HIGH" v={hero.high != null ? "$" + fmt(hero.high, 0) : "—"} />
          <Stat label="LOW" v={hero.low != null ? "$" + fmt(hero.low, 0) : "—"} />
          <Stat label="YES PEAK" v={hero.yesPeak != null ? (hero.yesPeak * 100).toFixed(1) + "¢" : "—"} />
          <Stat label="YES TROUGH" v={hero.yesTrough != null ? (hero.yesTrough * 100).toFixed(1) + "¢" : "—"} />
          <Stat label="VOLUME" v={window.total_volume != null ? "$" + fmtCompact(window.total_volume) : "—"} />
          <Stat label="TRADERS" v={window.traders != null ? window.traders.toLocaleString() : "—"} />
          <Stat label="TRADES" v={trades.length.toLocaleString()} />
          <Stat
            label={window.resolution ? "RESOLVED" : "OUTCOME"}
            v={window.resolution || "PENDING"}
            dir={window.resolution === "YES" ? "up" : window.resolution === "NO" ? "down" : ""}
          />
        </div>
      </div>

      <div className="pa-legend">
        <span className="label">SHOW</span>
        <Toggle on={layers.yes} onClick={() => toggle("yes")} color="#22c55e" label="YES" />
        <Toggle on={layers.no} onClick={() => toggle("no")} color="#ef4444" label="NO" />
        <Toggle on={layers.base} onClick={() => toggle("base")} color={coin.color || "#fff"} label={`${coin.symbol} PRICE`} />
        <Toggle on={layers.strike} onClick={() => toggle("strike")} color="#fbbf24" label="STRIKE" />

        {/* Trade bubbles dropdown */}
        <div className="bubble-menu-wrap">
          <button
            className={"leg-toggle bubble-trigger " + (bubblesAnyOn ? "on" : "off")}
            onClick={() => setBubblesOpen((o) => !o)}
          >
            <span className="bubble-glyph">
              <span className="bg-dot" style={{ background: "#22c55e" }}></span>
              <span className="bg-dot ring" style={{ borderColor: "#22c55e" }}></span>
              <span className="bg-dot" style={{ background: "#ef4444" }}></span>
              <span className="bg-dot ring" style={{ borderColor: "#ef4444" }}></span>
            </span>
            TRADE BUBBLES
            <span className="bubble-count mono">{bubblesOnCount}/4</span>
            <span className="caret">{bubblesOpen ? "▴" : "▾"}</span>
          </button>
          {bubblesOpen && (
            <div className="bubble-menu">
              <div className="bm-head mono">
                <span>BUBBLE FILTERS</span>
                <button className="bm-allbtn" onClick={() => setAllBubbles(!bubblesAllOn)}>
                  {bubblesAllOn ? "HIDE ALL" : "SHOW ALL"}
                </button>
              </div>
              <BubbleRow on={layers.yesBuy} onClick={() => toggle("yesBuy")} color="#22c55e" filled label="YES BUY" />
              <BubbleRow on={layers.yesSell} onClick={() => toggle("yesSell")} color="#22c55e" label="YES SELL" />
              <BubbleRow on={layers.noBuy} onClick={() => toggle("noBuy")} color="#ef4444" filled label="NO BUY" />
              <BubbleRow on={layers.noSell} onClick={() => toggle("noSell")} color="#ef4444" label="NO SELL" />
              <div className="bm-foot mono">Filled = BUY · Ring = SELL · Size = $ traded</div>
            </div>
          )}
        </div>

        <Toggle on={layers.volume} onClick={() => toggle("volume")} color="#b8bfcc" label="VOLUME" />
        <Toggle on={layers.heatmap} onClick={() => toggle("heatmap")} color="#9b6dff" label="ORDER ACCUMULATION" />

        {/* Zoom controls — same row as the SHOW toggles */}
        <div className="pa-zoom">
          <span className="label">ZOOM</span>
          <button className="btn tiny ghost" onClick={zoomOut} title="Zoom out">−</button>
          <button className="btn tiny ghost" onClick={zoomReset} title="Reset zoom">RESET</button>
          <button className="btn tiny ghost" onClick={zoomIn} title="Zoom in">+</button>
        </div>
      </div>

      <div className="anal-grid">
        <div className="anal-chart-col">
          <AnalysisChart
            ticks={ticks}
            trades={trades}
            heatmap={heatmap}
            outages={outages}
            startsAt={window.starts_at}
            endsAt={window.ends_at}
            strike={window.strike}
            baseColor={coin.color || "#fff"}
            layers={layers}
            zoom={zoom}
            height={560}
          />
          <div className="pa-trades-strip">
            <TradesTable trades={trades} />
          </div>
        </div>
        <div className="anal-rail">
          <OrderStatsRail stats={stats} />
        </div>
      </div>

      <div className="frame-bottom">
        <span className="seg"><span className="dot"></span>HISTORICAL ANALYSIS</span>
        <span className="seg"><span className="dot"></span>{trades.length} TRADES · {window.total_volume != null ? "$" + fmtCompact(window.total_volume) : "—"} VOL</span>
        <span className="spacer"></span>
        <span><span className="kbd">Esc</span> back</span>
      </div>

      <style>{`
        .pa-hero { display: flex; padding: 16px 24px; gap: 24px; border-bottom: 1px solid var(--line); background: var(--bg-1); flex-shrink: 0; align-items: stretch; }
        .pa-hero-left { flex: 1; min-width: 0; }
        .pa-mark { display: flex; gap: 16px; align-items: center; }
        .pa-q { font-size: 22px; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.01em; line-height: 1.25; }
        .pa-meta { display: flex; gap: 6px; font-size: 11px; align-items: center; flex-wrap: wrap; }
        .pa-meta .dim { color: var(--fg-3); }
        .pa-hero-stats { display: grid; grid-template-columns: repeat(10, minmax(70px, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); flex-shrink: 0; }
        .pa-stat { background: var(--bg-1); padding: 8px 12px; }
        .pa-stat .label { font-size: 9px; }
        .pa-stat .v { font-family: var(--font-mono); font-size: 13px; margin-top: 3px; color: var(--fg-0); white-space: nowrap; }
        .pa-stat.up .v { color: var(--up); }
        .pa-stat.down .v { color: var(--down); }
        @media (max-width: 1500px) { .pa-hero-stats { grid-template-columns: repeat(5, 1fr); } }
        .pa-legend { display: flex; gap: 6px; align-items: center; padding: 8px 24px; background: var(--bg-1); border-bottom: 1px solid var(--line); flex-shrink: 0; flex-wrap: wrap; }
        .pa-legend .label { margin-right: 8px; }
        .leg-toggle { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; background: var(--bg-2); border: 1px solid var(--line); font-size: 11px; font-family: var(--font-mono); letter-spacing: 0.04em; cursor: pointer; transition: all 120ms; user-select: none; }
        .leg-toggle:hover { background: var(--bg-3); }
        .leg-toggle.off { opacity: 0.4; text-decoration: line-through; }
        .leg-toggle .swatch { width: 14px; height: 2px; }
        .pa-trades-strip { border-top: 1px solid var(--line); flex-shrink: 0; height: 240px; }
        .pa-zoom {
          display: inline-flex; align-items: center; gap: 4px;
          margin-left: auto;
          /* Align with chart right edge — pull left by the rail width so the
             zoom buttons sit above the graph, not above ORDER STATS. */
          margin-right: 340px;
        }
        @media (max-width: 1100px) { .pa-zoom { margin-right: 300px; } }
        .pa-zoom .label { margin-right: 6px; }
        .pa-zoom .btn { min-width: 28px; }

        /* Bubble dropdown */
        .bubble-menu-wrap { position: relative; }
        .bubble-trigger { display: inline-flex; align-items: center; gap: 8px; padding-right: 8px !important; }
        .bubble-glyph { display: inline-flex; gap: 2px; align-items: center; }
        .bg-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
        .bg-dot.ring { background: transparent !important; border: 1.5px solid; }
        .bubble-count { font-size: 9px; color: var(--fg-3); padding: 1px 4px; background: var(--bg-1); border: 1px solid var(--line); }
        .caret { font-size: 9px; color: var(--fg-3); }
        .bubble-menu {
          position: absolute; top: calc(100% + 6px); left: 0;
          background: var(--bg-1); border: 1px solid var(--line-2);
          padding: 4px; min-width: 220px; z-index: 50;
          box-shadow: 0 8px 24px rgba(0,0,0,0.6);
        }
        .bm-head { display: flex; justify-content: space-between; align-items: center; padding: 6px 8px 8px; font-size: 9px; color: var(--fg-3); letter-spacing: 0.12em; border-bottom: 1px solid var(--line); margin-bottom: 4px; }
        .bm-allbtn { background: transparent; border: 1px solid var(--line); color: var(--fg-2); padding: 2px 6px; font-family: var(--font-mono); font-size: 9px; cursor: pointer; letter-spacing: 0.08em; }
        .bm-allbtn:hover { color: var(--fg-0); border-color: var(--line-2); }
        .bm-row { display: flex; align-items: center; gap: 10px; padding: 5px 8px; cursor: pointer; user-select: none; transition: background 100ms; }
        .bm-row:hover { background: var(--bg-2); }
        .bm-row.off { opacity: 0.45; }
        .bm-check { width: 12px; font-family: var(--font-mono); font-size: 11px; color: var(--fg-0); }
        .bm-bubble { width: 12px; height: 12px; border-radius: 50%; border: 1.5px solid; flex-shrink: 0; }
        .bm-label { font-size: 11px; letter-spacing: 0.04em; }
        .bm-foot { font-size: 9px; color: var(--fg-3); padding: 6px 8px; border-top: 1px solid var(--line); margin-top: 4px; letter-spacing: 0.04em; }
      `}</style>
    </>
  );
}

function Stat({ label, v, dir }: { label: string; v: string; dir?: string }) {
  return (
    <div className={"pa-stat " + (dir || "")}>
      <div className="label">{label}</div>
      <div className="v">{v}</div>
    </div>
  );
}

function Toggle({ on, onClick, color, label }: { on: boolean; onClick: () => void; color: string; label: string }) {
  return (
    <span className={"leg-toggle " + (on ? "on" : "off")} onClick={onClick}>
      <span className="swatch" style={{ background: color }}></span>
      {label}
    </span>
  );
}

function BubbleRow({ on, onClick, color, filled, label }: {
  on: boolean; onClick: () => void; color: string; filled?: boolean; label: string;
}) {
  return (
    <div className={"bm-row " + (on ? "on" : "off")} onClick={onClick}>
      <span className="bm-check">{on ? "✓" : ""}</span>
      <span
        className="bm-bubble"
        style={filled ? { background: color, borderColor: color } : { background: "transparent", borderColor: color }}
      ></span>
      <span className="bm-label mono">{label}</span>
    </div>
  );
}
