import { useEffect, useMemo, useState } from "react";
import { api, type Network } from "../api";
import { fmtCompact } from "../lib/format";

export function Networks({
  user,
  onPick,
  onLogout,
}: {
  user: string;
  onPick: (n: Network) => void;
  onLogout: () => void;
}) {
  const [networks, setNetworks] = useState<Network[]>([]);
  const [filter, setFilter] = useState("");
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    api.networks().then(setNetworks).catch(console.error);
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const filtered = useMemo(() => {
    if (!filter) return networks;
    const f = filter.toLowerCase();
    return networks.filter((n) => n.name.toLowerCase().includes(f) || n.slug.toLowerCase().includes(f));
  }, [filter, networks]);

  const enabledCount = networks.filter((n) => n.enabled).length;

  return (
    <>
      <div className="frame-top">
        <div className="brand"><span className="dot">●</span>TRACE TERMINAL</div>
        <div className="crumb"><span className="cur">NETWORKS</span></div>
        <div className="ticker">
          <div className="session"><div className="live"></div>FEED LIVE</div>
          <span className="muted mono">{user.toUpperCase()}</span>
          <button className="btn ghost sm" onClick={onLogout}>SIGN OUT</button>
        </div>
      </div>

      <div className="net-stage">
        <div className="net-head">
          <div>
            <div className="label">SELECT NETWORK</div>
            <h1 className="net-title">Choose where to look.</h1>
            <p className="net-subtitle">
              Pick a network to browse its markets and historical depth.
              <span className="dim"> All data is read-only — TRACE is an analysis terminal, not an execution venue.</span>
            </p>
          </div>
          <div className="net-search-wrap">
            <input
              className="input mono"
              placeholder="// filter networks…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              autoFocus
            />
            <span className="net-search-kbd"><span className="kbd">/</span></span>
          </div>
        </div>

        <div className="net-grid">
          {filtered.map((n) => (
            <NetworkCard key={n.slug} net={n} onPick={() => onPick(n)} />
          ))}
        </div>

        <div className="net-foot">
          <div className="net-foot-grid">
            <FootStat label="NETWORKS" v={String(networks.length)} />
            <FootStat label="ENABLED" v={String(enabledCount)} />
            <FootStat label="DISABLED" v={String(networks.length - enabledCount)} />
            <FootStat label="UPDATED" v={now.toTimeString().slice(0, 8)} />
          </div>
        </div>
      </div>

      <div className="frame-bottom">
        <span className="seg"><span className="dot"></span>FEED OK</span>
        <span className="seg"><span className="dot"></span>AUTHED · {user}</span>
        <span className="spacer"></span>
        <span><span className="kbd">↵</span> select · <span className="kbd">/</span> filter</span>
      </div>

      <style>{`
        .net-stage { flex: 1; padding: 32px 40px 16px; overflow: auto; display: flex; flex-direction: column; gap: 24px; position: relative; }
        .net-stage::before {
          content: ''; position: absolute; inset: 0;
          background-image: linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px);
          background-size: 80px 80px; background-position: -1px -1px; opacity: 0.4; pointer-events: none;
        }
        .net-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; position: relative; }
        .net-title { font-size: 36px; font-weight: 600; margin: 6px 0 8px; letter-spacing: -0.02em; }
        .net-subtitle { color: var(--fg-1); margin: 0; font-size: 13px; max-width: 60ch; }
        .net-search-wrap { position: relative; width: 320px; }
        .net-search-kbd { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); }
        .net-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; position: relative; }
        .net-card {
          background: var(--bg-1); border: 1px solid var(--line); padding: 18px; cursor: pointer;
          position: relative; display: flex; flex-direction: column; gap: 14px;
          transition: border-color 120ms, background 120ms; overflow: hidden;
        }
        .net-card.disabled { opacity: 0.55; cursor: not-allowed; }
        .net-card::before {
          content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
          background: var(--accent-color, var(--accent)); opacity: 0; transition: opacity 120ms;
        }
        .net-card:hover { border-color: var(--line-3); background: var(--bg-2); }
        .net-card:hover::before { opacity: 1; }
        .net-card-head { display: flex; align-items: flex-start; gap: 12px; }
        .net-glyph {
          width: 44px; height: 44px; border: 1px solid var(--line-2); background: var(--bg-2);
          display: flex; align-items: center; justify-content: center;
          font-family: var(--font-mono); font-weight: 700; font-size: 14px; flex-shrink: 0;
        }
        .net-name { font-size: 17px; font-weight: 600; color: var(--fg-0); line-height: 1; margin-bottom: 4px; }
        .net-tagline { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.06em; color: var(--fg-2); }
        .net-card-stats { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px dashed var(--line); padding-top: 12px; gap: 8px; }
        .net-stat .label { display: block; font-size: 9px; }
        .net-stat .v { font-family: var(--font-mono); font-size: 12px; color: var(--fg-0); margin-top: 2px; }
        .net-card-cta {
          position: absolute; right: 16px; top: 16px; font-family: var(--font-mono);
          font-size: 10px; color: var(--fg-3); letter-spacing: 0.14em;
          display: flex; align-items: center; gap: 4px; transition: color 120ms;
        }
        .net-card:hover .net-card-cta { color: var(--accent); }
        .net-foot { margin-top: auto; padding-top: 16px; border-top: 1px solid var(--line); position: relative; }
        .net-foot-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; }
        .foot-stat { padding: 12px 16px; border-right: 1px solid var(--line); }
        .foot-stat:last-child { border-right: none; }
        .foot-stat .label { font-size: 9px; }
        .foot-stat .v { font-family: var(--font-mono); font-size: 18px; color: var(--fg-0); margin-top: 4px; letter-spacing: -0.01em; }
        .net-disabled-tag { position: absolute; top: 16px; right: 16px; font-family: var(--font-mono); font-size: 9px; letter-spacing: 0.14em; color: var(--fg-3); border: 1px solid var(--line-2); padding: 2px 6px; }
      `}</style>
    </>
  );
}

function NetworkCard({ net, onPick }: { net: Network; onPick: () => void }) {
  const meta = (net.meta || {}) as { mcap?: number; tvl?: number; tps?: string; blockTime?: string; symbol?: string };
  return (
    <div
      className={"net-card" + (net.enabled ? "" : " disabled")}
      style={{ ["--accent-color" as string]: net.color || "var(--accent)" }}
      onClick={onPick}
    >
      <div className="net-card-head">
        <div className="net-glyph" style={{ color: net.color || "var(--fg-0)" }}>{(meta.symbol || net.slug.slice(0, 3)).toUpperCase()}</div>
        <div style={{ flex: 1 }}>
          <div className="net-name">{net.name}</div>
          <div className="net-tagline">{net.tagline}</div>
        </div>
      </div>
      {net.enabled ? (
        <div className="net-card-cta"><span>OPEN</span><span>→</span></div>
      ) : (
        <div className="net-disabled-tag">NO DATA</div>
      )}
      <div className="net-card-stats">
        <div className="net-stat"><span className="label">MCAP</span><span className="v">{meta.mcap ? "$" + fmtCompact(meta.mcap) : "—"}</span></div>
        <div className="net-stat"><span className="label">TVL</span><span className="v">{meta.tvl ? "$" + fmtCompact(meta.tvl) : "—"}</span></div>
        <div className="net-stat"><span className="label">TPS</span><span className="v">{meta.tps || "—"}</span></div>
        <div className="net-stat"><span className="label">BLOCK</span><span className="v">{meta.blockTime || "—"}</span></div>
      </div>
    </div>
  );
}

function FootStat({ label, v }: { label: string; v: string }) {
  return (
    <div className="foot-stat">
      <div className="label">{label}</div>
      <div className="v mono">{v}</div>
    </div>
  );
}
