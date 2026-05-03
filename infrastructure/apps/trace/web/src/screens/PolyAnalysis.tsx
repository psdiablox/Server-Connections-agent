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
    yes: true, no: true, base: true, strike: true, heatmap: true, bubbles: true, volume: true,
  });
  const toggle = (k: keyof ChartLayers) => setLayers((v) => ({ ...v, [k]: !v[k] }));

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
        <Toggle on={layers.bubbles} onClick={() => toggle("bubbles")} color="#9ca3af" label="TRADE BUBBLES" />
        <Toggle on={layers.volume} onClick={() => toggle("volume")} color="#b8bfcc" label="VOLUME" />
        <Toggle on={layers.heatmap} onClick={() => toggle("heatmap")} color="#9b6dff" label="ORDER ACCUMULATION" />
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
