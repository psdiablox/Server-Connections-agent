import { useEffect, useMemo, useState } from "react";
import { api, type Coin, type Network, type WindowList, type WindowSummary } from "../api";
import { fmt, fmtCompact, fmtLocalWindow, fmtWindowET, localTZ } from "../lib/format";

const TFS = [
  { id: "5m", label: "5 MIN" },
  { id: "15m", label: "15 MIN" },
  { id: "1h", label: "1 HOUR" },
  { id: "1d", label: "1 DAY" },
];

export function PolyWindows({
  network,
  coin,
  onBack,
  onHome,
  onPick,
}: {
  network: Network;
  coin: Coin;
  onBack: () => void;
  onHome: () => void;
  onPick: (w: WindowSummary) => void;
}) {
  const [tf, setTf] = useState("5m");
  const [statusFilter, setStatusFilter] = useState<"all" | "live" | "upcoming" | "ended">("all");
  const [resFilter, setResFilter] = useState<"all" | "yes" | "no">("all");
  const [sort, setSort] = useState<"time" | "vol" | "traders">("time");
  const [data, setData] = useState<WindowList | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .windows(network.slug, coin.slug, {
        tf,
        status: statusFilter,
        resolution: resFilter,
        sort,
        limit: 500,
      })
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [network.slug, coin.slug, tf, statusFilter, resFilter, sort]);

  const counts = data?.counts || { all: 0, live: 0, upcoming: 0, ended: 0 };

  return (
    <>
      <div className="frame-top">
        <div className="brand"><span className="dot">●</span>TRACE</div>
        <div className="crumb">
          <a onClick={onHome}>NETWORKS</a><span className="sep">/</span>
          <a onClick={onBack} style={{ color: network.color || undefined }}>{network.name.toUpperCase()}</a>
          <span className="sep">/</span>
          <span className="cur" style={{ color: coin.color || undefined }}>{coin.symbol}</span>
          <span className="sep">/</span>
          <span className="cur">WINDOWS</span>
        </div>
      </div>

      <div className="pw-head">
        <div className="pw-head-left">
          <div className="poly-coin-glyph" style={{ borderColor: coin.color || undefined, color: coin.color || undefined, width: 48, height: 48, fontSize: 12 }}>{coin.symbol}</div>
          <div>
            <h1 className="pw-title">{coin.name} prediction windows</h1>
            <div className="pw-sub mono">
              <span>SPOT ${coin.base_price ? fmt(coin.base_price, coin.base_price < 1 ? 4 : 2) : "—"}</span>
              <span className="dim">·</span>
              <span>{counts.live || 0} LIVE · {counts.upcoming || 0} UPCOMING · {counts.ended || 0} ENDED</span>
            </div>
          </div>
        </div>
        <div className="pw-tfs">
          {TFS.map((t) => (
            <button key={t.id} className={"btn " + (tf === t.id ? "primary" : "ghost")} onClick={() => setTf(t.id)}>{t.label}</button>
          ))}
        </div>
      </div>

      <div className="pw-filters">
        <div className="pw-segment">
          {(["all", "live", "upcoming", "ended"] as const).map((s) => (
            <button
              key={s}
              className={"btn tiny " + (statusFilter === s ? "active" : "ghost")}
              onClick={() => setStatusFilter(s)}
            >{s.toUpperCase()} · {counts[s] || 0}</button>
          ))}
        </div>
        <div className="pw-segment">
          <span className="mono dim" style={{ fontSize: 10, marginRight: 4 }}>RESOLVED</span>
          {(["all", "yes", "no"] as const).map((s) => (
            <button key={s} className={"btn tiny " + (resFilter === s ? "active" : "ghost")} onClick={() => setResFilter(s)}>{s.toUpperCase()}</button>
          ))}
        </div>
        <div className="pw-segment" style={{ marginLeft: "auto" }}>
          <span className="mono dim" style={{ fontSize: 10, marginRight: 4 }}>SORT</span>
          {(["time", "vol", "traders"] as const).map((s) => (
            <button key={s} className={"btn tiny " + (sort === s ? "active" : "ghost")} onClick={() => setSort(s)}>{s.toUpperCase()}</button>
          ))}
        </div>
      </div>

      <div className="pw-table-wrap">
        <div className="pw-table-head mono">
          <div>STATUS</div>
          <div>WINDOW (ET)</div>
          <div>LOCAL</div>
          <div className="num">STRIKE</div>
          <div className="num">YES</div>
          <div className="num">NO</div>
          <div className="num">VOLUME</div>
          <div className="num">TRADERS</div>
          <div>RESOLUTION</div>
          <div></div>
        </div>
        <div className="pw-table-body">
          {loading && <div className="pw-empty mono">// loading…</div>}
          {!loading && (data?.items.length || 0) === 0 && (
            <div className="pw-empty mono">// no windows yet — collector hasn't seen any</div>
          )}
          {data?.items.map((w) => <WindowRow key={w.id} w={w} onPick={onPick} />)}
        </div>
      </div>

      <div className="frame-bottom">
        <span className="seg"><span className="dot"></span>{coin.symbol} · {tf.toUpperCase()}</span>
        <span className="seg"><span className="dot"></span>{data?.items.length || 0} of {data?.total || 0}</span>
        <span className="spacer"></span>
        <span><span className="kbd">↵</span> open · <span className="kbd">Esc</span> back</span>
      </div>

      <style>{`
        .pw-head { display: flex; align-items: center; gap: 24px; padding: 20px 32px; background: var(--bg-1); border-bottom: 1px solid var(--line); flex-shrink: 0; }
        .pw-head-left { display: flex; align-items: center; gap: 16px; flex: 1; }
        .pw-title { font-size: 22px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
        .pw-sub { display: flex; gap: 8px; font-size: 11px; margin-top: 6px; align-items: center; }
        .pw-sub .dim { color: var(--fg-3); }
        .pw-tfs { display: flex; gap: 4px; }
        .pw-filters { display: flex; gap: 12px; align-items: center; padding: 10px 32px; background: var(--bg-1); border-bottom: 1px solid var(--line); flex-shrink: 0; flex-wrap: wrap; }
        .pw-segment { display: flex; align-items: center; gap: 2px; }
        .pw-table-wrap { flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 16px 32px; background: var(--bg-0); overflow: hidden; }
        .pw-table-head, .pw-row {
          display: grid;
          grid-template-columns: 90px 230px 200px 80px 70px 70px 110px 90px 110px 50px;
          align-items: center; gap: 12px; padding: 0 14px;
        }
        .pw-table-head { height: 32px; font-size: 9px; color: var(--fg-3); border-bottom: 1px solid var(--line); background: var(--bg-1); }
        .pw-table-head .num { text-align: right; }
        .pw-table-body { flex: 1; overflow-y: auto; overflow-x: hidden; background: var(--bg-1); border: 1px solid var(--line); border-top: none; }
        .pw-row { height: 48px; font-family: var(--font-mono); font-size: 12px; border-bottom: 1px solid var(--line); cursor: pointer; }
        .pw-row:hover { background: var(--bg-2); }
        .pw-row .num { text-align: right; }
        .pw-empty { padding: 40px; text-align: center; color: var(--fg-3); }
        .pw-status { display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; }
        .pw-status .dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
        .pw-status.live { background: rgba(34,197,94,0.12); color: #22c55e; }
        .pw-status.live .dot { background: #22c55e; animation: pulse 1.5s infinite; }
        .pw-status.upcoming { background: rgba(6,182,212,0.12); color: #06b6d4; }
        .pw-status.upcoming .dot { background: #06b6d4; }
        .pw-status.ended { background: rgba(107,114,128,0.12); color: #9ca3af; }
        .pw-status.ended .dot { background: #6b7280; }
        .pw-res { display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; }
        .pw-res.yes { background: rgba(34,197,94,0.15); color: #22c55e; }
        .pw-res.no { background: rgba(239,68,68,0.15); color: #ef4444; }
        .pw-res.pending { color: var(--fg-3); }
        .pw-yes { color: #22c55e; }
        .pw-no { color: #ef4444; }
        @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.4;} }
      `}</style>
    </>
  );
}

function WindowRow({ w, onPick }: { w: WindowSummary; onPick: (w: WindowSummary) => void }) {
  const local = fmtLocalWindow(w.starts_at, w.ends_at);
  const yes = w.last_yes ?? 0;
  return (
    <div className="pw-row" onClick={() => onPick(w)}>
      <div>
        <span className={`pw-status ${w.status}`}>
          <span className="dot"></span>
          {w.status.toUpperCase()}
        </span>
      </div>
      <div>{fmtWindowET(w.starts_at, w.ends_at)} <span style={{ color: "var(--fg-3)", fontSize: 10 }}>ET</span></div>
      <div>{local} <span style={{ color: "var(--fg-3)", fontSize: 10 }}>{localTZ()}</span></div>
      <div className="num">{w.strike != null ? "$" + fmt(w.strike, w.strike < 1 ? 4 : (w.strike < 100 ? 2 : 0)) : "—"}</div>
      <div className={"num " + (yes >= 0.5 ? "pw-yes" : "pw-no")}>
        {w.status === "upcoming" || w.last_yes == null ? "—" : (yes * 100).toFixed(1) + "¢"}
      </div>
      <div className={"num " + (yes < 0.5 ? "pw-yes" : "pw-no")}>
        {w.status === "upcoming" || w.last_yes == null ? "—" : ((1 - yes) * 100).toFixed(1) + "¢"}
      </div>
      <div className="num">{w.total_volume != null ? "$" + fmtCompact(w.total_volume) : "—"}</div>
      <div className="num">{w.traders != null ? w.traders.toLocaleString() : "—"}</div>
      <div>
        {w.resolution
          ? <span className={`pw-res ${w.resolution.toLowerCase()}`}>{w.resolution}</span>
          : <span className="pw-res pending">PENDING</span>}
      </div>
      <div style={{ color: "var(--fg-3)", textAlign: "right" }}>→</div>
    </div>
  );
}
