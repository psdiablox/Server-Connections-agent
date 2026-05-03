import type { Coin, Network } from "../api";

export function EmptyState({
  network,
  coin,
  message,
  subtitle,
  onHome,
  onBack,
}: {
  network: Network;
  coin?: Coin;
  message: string;
  subtitle: string;
  onHome: () => void;
  onBack?: () => void;
}) {
  return (
    <>
      <div className="frame-top">
        <div className="brand"><span className="dot">●</span>TRACE</div>
        <div className="crumb">
          <a onClick={onHome}>NETWORKS</a><span className="sep">/</span>
          <span className="cur" style={{ color: network.color || undefined }}>{network.name.toUpperCase()}</span>
          {coin && (
            <>
              <span className="sep">/</span>
              <span className="cur" style={{ color: coin.color || undefined }}>{coin.symbol}</span>
            </>
          )}
        </div>
      </div>

      <div className="grid-bg" style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="panel" style={{ width: 480 }}>
          <div className="panel-head"><span className="title">EMPTY DATASET</span></div>
          <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="mono" style={{ fontSize: 14, color: "var(--fg-1)" }}>{message}</div>
            <div className="dim" style={{ fontSize: 12, lineHeight: 1.6 }}>{subtitle}</div>
            <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
              {onBack && <button className="btn ghost sm" onClick={onBack}>← BACK</button>}
              <button className="btn ghost sm" onClick={onHome}>NETWORKS</button>
            </div>
          </div>
        </div>
      </div>

      <div className="frame-bottom">
        <span className="seg"><span className="dot warn"></span>NO DATA</span>
        <span className="spacer"></span>
      </div>
    </>
  );
}
