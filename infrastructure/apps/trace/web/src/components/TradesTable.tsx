import { useMemo, useState } from "react";
import type { Trade } from "../api";
import { fmt } from "../lib/format";

type SortKey = "time" | "outcome" | "side" | "price" | "size" | "value";
type Dir = "asc" | "desc";

const COLS: { key: SortKey; label: string; num?: boolean; flex?: number }[] = [
  { key: "time", label: "TIME" },
  { key: "outcome", label: "OUTCOME" },
  { key: "side", label: "SIDE" },
  { key: "price", label: "PRICE", num: true },
  { key: "size", label: "SIZE", num: true },
];

export function TradesTable({ trades }: { trades: Trade[] }) {
  const [sort, setSort] = useState<SortKey>("time");
  const [dir, setDir] = useState<Dir>("desc");

  const onHeader = (k: SortKey) => {
    if (sort === k) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSort(k); setDir("desc"); }
  };

  const sorted = useMemo(() => {
    const arr = trades.slice();
    const mul = dir === "asc" ? 1 : -1;
    arr.sort((a, b) => {
      let av: number | string;
      let bv: number | string;
      switch (sort) {
        case "time": av = +new Date(a.t); bv = +new Date(b.t); break;
        case "outcome": av = a.outcome; bv = b.outcome; break;
        case "side": av = a.side; bv = b.side; break;
        case "price": av = a.price; bv = b.price; break;
        case "size": av = a.size; bv = b.size; break;
        case "value": av = a.price * a.size; bv = b.price * b.size; break;
      }
      if (av < bv) return -1 * mul;
      if (av > bv) return 1 * mul;
      return 0;
    });
    return arr;
  }, [trades, sort, dir]);

  return (
    <div className="panel" style={{ height: "100%" }}>
      <div className="panel-head">
        <span className="title">TRADES · {trades.length.toLocaleString()}</span>
        <span className="dim mono" style={{ marginLeft: "auto", fontSize: 10 }}>click a header to sort</span>
      </div>
      <div className="panel-body">
        <div className="t-row head trade-row">
          {COLS.map((c) => (
            <div
              key={c.key}
              className={"sort-head" + (c.num ? " num" : "") + (sort === c.key ? " active" : "")}
              onClick={() => onHeader(c.key)}
            >
              {c.label}
              {sort === c.key && <span className="sort-arrow"> {dir === "asc" ? "▲" : "▼"}</span>}
            </div>
          ))}
        </div>
        {trades.length === 0 && (
          <div className="mono dim" style={{ padding: 16, fontSize: 11 }}>// no trades yet</div>
        )}
        {sorted.map((t, i) => (
          <div key={i} className="t-row trade-row">
            <div>{new Date(t.t).toISOString().slice(11, 19)}</div>
            <div className={t.outcome === "YES" ? "up" : "down"}>{t.outcome}</div>
            <div>{t.side}</div>
            <div style={{ textAlign: "right" }}>{(t.price * 100).toFixed(2)}¢</div>
            <div style={{ textAlign: "right" }}>${fmt(t.price * t.size, 2)}</div>
          </div>
        ))}
      </div>
      <style>{`
        .trade-row { grid-template-columns: 120px 70px 60px 100px 100px; }
        .sort-head { cursor: pointer; user-select: none; display: inline-flex; align-items: center; gap: 4px; transition: color 80ms; }
        .sort-head.num { justify-content: flex-end; }
        .sort-head:hover { color: var(--fg-1); }
        .sort-head.active { color: var(--fg-0); }
        .sort-arrow { font-size: 8px; }
      `}</style>
    </div>
  );
}
