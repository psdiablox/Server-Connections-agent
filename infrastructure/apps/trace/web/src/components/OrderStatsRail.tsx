import type { OrderStats } from "../api";
import { fmt, fmtCompact } from "../lib/format";

export function OrderStatsRail({ stats }: { stats: OrderStats | null }) {
  return (
    <div className="panel" style={{ height: "100%" }}>
      <div className="panel-head"><span className="title">ORDER STATS</span></div>
      <div className="panel-body" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 12 }}>
        {!stats && <div className="mono dim" style={{ fontSize: 11 }}>// no data</div>}
        {stats && (
          <>
            <Group title="YES">
              <Row k="BUY" v={stats.yes_buy_count} sub={"$" + fmtCompact(stats.yes_buy_volume)} color="var(--up)" />
              <Row k="SELL" v={stats.yes_sell_count} sub={"$" + fmtCompact(stats.yes_sell_volume)} color="var(--up)" />
            </Group>
            <Group title="NO">
              <Row k="BUY" v={stats.no_buy_count} sub={"$" + fmtCompact(stats.no_buy_volume)} color="var(--down)" />
              <Row k="SELL" v={stats.no_sell_count} sub={"$" + fmtCompact(stats.no_sell_volume)} color="var(--down)" />
            </Group>
            <Group title="AGGREGATE">
              <Row k="LARGEST" v={stats.largest_trade != null ? "$" + fmt(stats.largest_trade, 2) : "—"} />
              <Row k="AVG SIZE" v={stats.avg_trade != null ? "$" + fmt(stats.avg_trade, 2) : "—"} />
            </Group>
          </>
        )}
      </div>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 6 }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>{children}</div>
    </div>
  );
}

function Row({ k, v, sub, color }: { k: string; v: number | string; sub?: string; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
      <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>{k}</span>
      <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
        <span className="mono" style={{ color: color || "var(--fg-0)", fontSize: 13 }}>{typeof v === "number" ? v.toLocaleString() : v}</span>
        {sub && <span className="mono dim" style={{ fontSize: 10 }}>{sub}</span>}
      </span>
    </div>
  );
}
