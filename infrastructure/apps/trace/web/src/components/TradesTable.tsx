import type { Trade } from "../api";
import { fmt } from "../lib/format";

export function TradesTable({ trades }: { trades: Trade[] }) {
  return (
    <div className="panel" style={{ height: "100%" }}>
      <div className="panel-head">
        <span className="title">TRADES · {trades.length.toLocaleString()}</span>
      </div>
      <div className="panel-body">
        <div className="t-row head" style={{ gridTemplateColumns: "120px 60px 60px 100px 100px" }}>
          <div>TIME</div>
          <div>OUTCOME</div>
          <div>SIDE</div>
          <div style={{ textAlign: "right" }}>PRICE</div>
          <div style={{ textAlign: "right" }}>SIZE</div>
        </div>
        {trades.length === 0 && (
          <div className="mono dim" style={{ padding: 16, fontSize: 11 }}>// no trades yet</div>
        )}
        {trades.map((t, i) => (
          <div key={i} className="t-row" style={{ gridTemplateColumns: "120px 60px 60px 100px 100px" }}>
            <div>{new Date(t.t).toISOString().slice(11, 19)}</div>
            <div className={t.outcome === "YES" ? "up" : "down"}>{t.outcome}</div>
            <div>{t.side}</div>
            <div style={{ textAlign: "right" }}>{(t.price * 100).toFixed(2)}¢</div>
            <div style={{ textAlign: "right" }}>${fmt(t.price * t.size, 2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
