import { useEffect, useState } from "react";
import { api, type Coin, type Network } from "../api";
import { fmt, fmtCompact } from "../lib/format";

export function PolyCoins({
  network,
  onPick,
  onBack,
}: {
  network: Network;
  onPick: (c: Coin) => void;
  onBack: () => void;
}) {
  const [coins, setCoins] = useState<Coin[]>([]);

  useEffect(() => {
    api.networkCoins(network.slug).then(setCoins).catch(console.error);
  }, [network.slug]);

  return (
    <>
      <div className="frame-top">
        <div className="brand"><span className="dot">●</span>TRACE</div>
        <div className="crumb">
          <a onClick={onBack}>NETWORKS</a><span className="sep">/</span>
          <span className="cur" style={{ color: network.color || undefined }}>{network.name.toUpperCase()}</span>
          <span className="sep">/</span>
          <span className="cur">SELECT COIN</span>
        </div>
      </div>

      <div className="poly-coins-wrap">
        <div className="poly-coins-head">
          <div>
            <h1 className="poly-coins-title">Select a coin to analyze</h1>
            <p className="poly-coins-sub">Polymarket prediction windows · binary YES/NO outcomes</p>
          </div>
        </div>

        <div className="poly-coins-grid">
          {coins.map((coin, i) => {
            const meta = (coin.meta || {}) as { vol24?: number; marketCap?: number };
            return (
              <div
                key={coin.slug}
                className={"poly-coin-card" + (coin.enabled ? "" : " disabled")}
                onClick={() => onPick(coin)}
              >
                <div className="poly-coin-num mono">{String(i + 1).padStart(2, "0")}</div>
                <div className="poly-coin-glyph" style={{ borderColor: coin.color || "var(--line-2)", color: coin.color || "var(--fg-0)" }}>
                  {coin.symbol}
                </div>
                <div className="poly-coin-body">
                  <div className="poly-coin-name">{coin.name}</div>
                  <div className="poly-coin-px mono">${coin.base_price ? fmt(coin.base_price, coin.base_price < 1 ? 4 : 2) : "—"}</div>
                </div>
                <div className="poly-coin-stats">
                  <div><span className="dim">VOL 24H</span><span className="mono">{meta.vol24 ? "$" + fmtCompact(meta.vol24) : "—"}</span></div>
                  <div><span className="dim">MCAP</span><span className="mono">{meta.marketCap ? "$" + fmtCompact(meta.marketCap) : "—"}</span></div>
                  <div><span className="dim">STATUS</span><span className="mono" style={{ color: coin.enabled ? "var(--up)" : "var(--fg-3)" }}>{coin.enabled ? "ACTIVE" : "NO DATA"}</span></div>
                </div>
                <div className="poly-coin-arrow mono">→</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="frame-bottom">
        <span className="seg"><span className="dot"></span>POLYMARKET</span>
        <span className="spacer"></span>
        <span><span className="kbd">↵</span> select · <span className="kbd">Esc</span> back</span>
      </div>

      <style>{`
        .poly-coins-wrap { flex: 1; padding: 32px 40px; overflow-y: auto; background: var(--bg-0); }
        .poly-coins-head { margin-bottom: 24px; }
        .poly-coins-title { font-size: 28px; font-weight: 600; letter-spacing: -0.02em; margin: 0; }
        .poly-coins-sub { font-size: 13px; color: var(--fg-3); margin: 4px 0 0; }
        .poly-coins-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
          gap: 1px; background: var(--line); border: 1px solid var(--line);
        }
        .poly-coin-card {
          background: var(--bg-1); padding: 20px 24px;
          display: grid; grid-template-columns: 32px 64px 1fr auto 24px;
          gap: 16px; align-items: center; cursor: pointer; transition: background 120ms;
        }
        .poly-coin-card.disabled { opacity: 0.55; }
        .poly-coin-card:hover { background: var(--bg-2); }
        .poly-coin-num { color: var(--fg-3); font-size: 11px; }
        .poly-coin-glyph {
          width: 56px; height: 56px; display: flex; align-items: center; justify-content: center;
          border: 1px solid; font-family: var(--font-mono); font-weight: 700; font-size: 13px;
        }
        .poly-coin-name { font-size: 16px; font-weight: 600; }
        .poly-coin-px { font-size: 13px; color: var(--fg-2); margin-top: 2px; }
        .poly-coin-stats { display: grid; grid-template-columns: repeat(3, auto); gap: 16px; font-size: 11px; }
        .poly-coin-stats > div { display: flex; flex-direction: column; gap: 2px; }
        .poly-coin-stats .dim { font-size: 9px; letter-spacing: 0.1em; }
        .poly-coin-arrow { color: var(--fg-3); font-size: 18px; }
        .poly-coin-card:hover .poly-coin-arrow { color: var(--fg-0); }
      `}</style>
    </>
  );
}
