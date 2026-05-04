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
  const [sort, setSort] = useState<string>("time");
  const [dir, setDir] = useState<"asc" | "desc">("desc");
  const [data, setData] = useState<WindowList | null>(null);
  const [loading, setLoading] = useState(false);

  const onHeader = (key: string) => {
    if (sort === key) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSort(key); setDir("desc"); }
  };

  useEffect(() => {
    setLoading(true);
    api
      .windows(network.slug, coin.slug, {
        tf,
        status: statusFilter,
        resolution: resFilter,
        sort,
        dir,
        limit: 500,
      })
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [network.slug, coin.slug, tf, statusFilter, resFilter, sort, dir]);

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
          {([{ id: "all", label: "ALL" }, { id: "yes", label: "UP" }, { id: "no", label: "DOWN" }] as const).map((s) => (
            <button key={s.id} className={"btn tiny " + (resFilter === s.id ? "active" : "ghost")} onClick={() => setResFilter(s.id as "all" | "yes" | "no")}>{s.label}</button>
          ))}
        </div>
        <div className="pw-segment" style={{ marginLeft: "auto" }}>
          <span className="mono dim" style={{ fontSize: 10 }}>click any column header to sort</span>
        </div>
      </div>

      <div className="pw-table-wrap">
        <div className="pw-table-head mono">
          <SortHead label="STATUS"     k="status"   sort={sort} dir={dir} onClick={onHeader} />
          <SortHead label="WINDOW (ET)" k="time"     sort={sort} dir={dir} onClick={onHeader} />
          <SortHead label="LOCAL"      k="time"     sort={sort} dir={dir} onClick={onHeader} />
          <SortHead label="STRIKE"     k="strike"   sort={sort} dir={dir} onClick={onHeader} num />
          <SortHead label="BTC CLOSE"  k="close"    sort={sort} dir={dir} onClick={onHeader} num />
          <SortHead label="Δ%"         k="change"   sort={sort} dir={dir} onClick={onHeader} num />
          <SortHead label="VOLUME"     k="vol"      sort={sort} dir={dir} onClick={onHeader} num />
          <SortHead label="TRADES"     k="trades"   sort={sort} dir={dir} onClick={onHeader} num />
          <SortHead label="LARGEST"    k="largest"  sort={sort} dir={dir} onClick={onHeader} num />
          <SortHead label="AVG"        k="avg"      sort={sort} dir={dir} onClick={onHeader} num />
          <SortHead label="DATA"       k="coverage" sort={sort} dir={dir} onClick={onHeader} num />
          <SortHead label="RESULT"     k="result"   sort={sort} dir={dir} onClick={onHeader} />
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
          grid-template-columns: 80px 195px 165px 85px 85px 75px 75px 60px 75px 65px 65px 75px 30px;
          align-items: center; gap: 12px; padding: 0 14px;
        }
        .pw-table-head { height: 32px; font-size: 9px; color: var(--fg-3); border-bottom: 1px solid var(--line); background: var(--bg-1); }
        .pw-table-head .num { text-align: right; }
        .pw-table-body { flex: 1; overflow-y: auto; overflow-x: hidden; background: var(--bg-1); border: 1px solid var(--line); border-top: none; }
        .pw-row { height: 48px; font-family: var(--font-mono); font-size: 12px; border-bottom: 1px solid var(--line); cursor: pointer; }
        .pw-row:hover { background: var(--bg-2); }
        .pw-row .num { text-align: right; }
        .pw-empty { padding: 40px; text-align: center; color: var(--fg-3); }
        .sort-head {
          cursor: pointer; user-select: none;
          display: inline-flex; align-items: center; gap: 4px;
          transition: color 80ms;
        }
        .sort-head.num { justify-content: flex-end; }
        .sort-head:hover { color: var(--fg-1); }
        .sort-head.active { color: var(--fg-0); }
        .sort-arrow { font-size: 8px; }
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
        .pw-warn { color: #f59e0b; }
        @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.4;} }
      `}</style>
    </>
  );
}

function SortHead({
  label, k, sort, dir, onClick, num = false,
}: {
  label: string; k: string; sort: string; dir: "asc" | "desc";
  onClick: (k: string) => void; num?: boolean;
}) {
  const active = sort === k;
  return (
    <div
      className={"sort-head" + (num ? " num" : "") + (active ? " active" : "")}
      onClick={() => onClick(k)}
    >
      {label}
      {active && <span className="sort-arrow"> {dir === "asc" ? "▲" : "▼"}</span>}
    </div>
  );
}

function WindowRow({ w, onPick }: { w: WindowSummary; onPick: (w: WindowSummary) => void }) {
  const local = fmtLocalWindow(w.starts_at, w.ends_at);

  // Result derivation: prefer the explicit Polymarket resolution; otherwise
  // for ended markets compare close BTC to strike, falling back to last YES.
  let result: "YES" | "NO" | null = w.resolution;
  if (!result && w.status === "ended") {
    if (w.close_btc != null && w.strike != null) {
      result = w.close_btc > w.strike ? "YES" : w.close_btc < w.strike ? "NO" : null;
    } else if (w.last_yes != null) {
      result = w.last_yes >= 0.5 ? "YES" : "NO";
    }
  }

  // BTC close colour: green if it ended above strike, red if below.
  let closeClass = "";
  if (w.close_btc != null && w.strike != null) {
    closeClass = w.close_btc > w.strike ? "pw-yes" : w.close_btc < w.strike ? "pw-no" : "";
  }

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
      <div className={"num " + closeClass}>
        {w.close_btc != null ? "$" + fmt(w.close_btc, w.close_btc < 1 ? 4 : (w.close_btc < 100 ? 2 : 0)) : "—"}
      </div>
      <div className={"num " + closeClass}>
        {(() => {
          if (w.close_btc == null || w.strike == null || w.strike === 0) return "—";
          const pct = ((w.close_btc - w.strike) / w.strike) * 100;
          const sign = pct > 0 ? "+" : "";
          // 4 decimals for very small moves typical of 5-min BTC windows
          return `${sign}${pct.toFixed(pct === 0 || Math.abs(pct) >= 1 ? 2 : 4)}%`;
        })()}
      </div>
      <div className="num">{w.total_volume != null ? "$" + fmtCompact(w.total_volume) : "—"}</div>
      <div className="num">{w.trade_count != null ? w.trade_count.toLocaleString() : "—"}</div>
      <div className="num">{w.largest_trade != null ? "$" + fmtCompact(w.largest_trade) : "—"}</div>
      <div className="num">{w.avg_trade != null ? "$" + fmt(w.avg_trade, 2) : "—"}</div>
      <div className={"num " + (w.data_coverage_pct == null ? "" : w.data_coverage_pct >= 99.5 ? "pw-yes" : w.data_coverage_pct >= 90 ? "pw-warn" : "pw-no")}>
        {w.data_coverage_pct != null ? w.data_coverage_pct.toFixed(1) + "%" : "—"}
      </div>
      <div>
        {result
          ? <span className={`pw-res ${result.toLowerCase()}`}>{result === "YES" ? "UP" : "DOWN"}</span>
          : <span className="pw-res pending">{w.status === "ended" ? "—" : "PENDING"}</span>}
      </div>
      <div style={{ color: "var(--fg-3)", textAlign: "right" }}>→</div>
    </div>
  );
}
