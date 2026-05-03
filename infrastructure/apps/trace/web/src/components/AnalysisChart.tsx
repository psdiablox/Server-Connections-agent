import { useMemo, useRef, useState } from "react";
import type { Heatmap, Tick, Trade } from "../api";

export type ChartLayers = {
  yes: boolean;
  no: boolean;
  base: boolean;
  strike: boolean;
  heatmap: boolean;
  bubbles: boolean;
  volume: boolean;
};

type Props = {
  ticks: Tick[];
  trades: Trade[];
  heatmap: Heatmap | null;
  startsAt: string;
  endsAt: string;
  strike: number | null;
  baseColor: string;
  layers: ChartLayers;
  height?: number;
};

const M = { left: 56, right: 64, top: 16, bottom: 28, vol: 56 };
const PROB_TICKS = [0, 0.2, 0.4, 0.5, 0.6, 0.8, 1];

type Hover =
  | null
  | { kind: "cursor"; x: number; y: number }
  | { kind: "trade"; x: number; y: number; trade: Trade };

export function AnalysisChart({
  ticks,
  trades,
  heatmap,
  startsAt,
  endsAt,
  strike,
  baseColor,
  layers,
  height = 560,
}: Props) {
  const W = 1200;
  const innerH = height - M.top - M.bottom - (layers.volume ? M.vol : 0);
  const innerW = W - M.left - M.right;
  const volTop = M.top + innerH;

  const T0 = new Date(startsAt).getTime();
  const T1 = new Date(endsAt).getTime();
  const fullSpan = Math.max(1, T1 - T0);

  // Zoom state: visible range in [0..1] of the full window.
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

  const t0 = T0 + fullSpan * zoom.a;
  const t1 = T0 + fullSpan * zoom.b;
  const dt = Math.max(1, t1 - t0);

  const x = (ms: number) => M.left + ((ms - t0) / dt) * innerW;
  const xInv = (px: number) => t0 + ((px - M.left) / innerW) * dt;
  const yProb = (p: number) => M.top + (1 - p) * innerH;
  const yProbInv = (py: number) => 1 - (py - M.top) / innerH;

  // Lines from TRADES (truth), not from mid-snapshot averages — guarantees
  // bubbles align with their outcome's curve.
  const { yesLine, noLine } = useMemo(() => {
    const ys = trades
      .filter((t) => t.outcome === "YES")
      .sort((a, b) => +new Date(a.t) - +new Date(b.t));
    const ns = trades
      .filter((t) => t.outcome === "NO")
      .sort((a, b) => +new Date(a.t) - +new Date(b.t));
    return { yesLine: ys, noLine: ns };
  }, [trades]);

  const yesPath = useMemo(() => makeLinePath(yesLine, x, yProb), [yesLine, t0, dt, innerH]);
  const noPath = useMemo(() => makeLinePath(noLine, x, yProb), [noLine, t0, dt, innerH]);

  // Base price scale — symmetric around strike so STRIKE sits exactly on 50¢.
  const { yBase, baseMin, baseMax } = useMemo(() => {
    const bases = ticks.map((t) => t.base_price).filter((v): v is number => v != null);
    if (strike == null && bases.length === 0) {
      return { yBase: () => M.top + innerH / 2, baseMin: 0, baseMax: 0 };
    }
    if (strike != null) {
      const dataMax = bases.length ? Math.max(...bases) : strike;
      const dataMin = bases.length ? Math.min(...bases) : strike;
      const dev = Math.max(strike - dataMin, dataMax - strike, strike * 0.0005);
      const range = dev * 1.1;
      const mn = strike - range;
      const mx = strike + range;
      return {
        yBase: (v: number) => M.top + (1 - (v - mn) / (mx - mn)) * innerH,
        baseMin: mn,
        baseMax: mx,
      };
    }
    let mn = Math.min(...bases), mx = Math.max(...bases);
    if (mn === mx) { mn *= 0.999; mx *= 1.001; }
    const pad = (mx - mn) * 0.15;
    mn -= pad; mx += pad;
    return {
      yBase: (v: number) => M.top + (1 - (v - mn) / (mx - mn)) * innerH,
      baseMin: mn,
      baseMax: mx,
    };
  }, [ticks, strike, innerH]);

  const basePath = useMemo(() => {
    if (!ticks.length) return "";
    return ticks
      .filter((t) => t.base_price != null)
      .map((t, i) => {
        const xx = x(new Date(t.t).getTime());
        return `${i === 0 ? "M" : "L"} ${xx.toFixed(1)} ${yBase(t.base_price!).toFixed(1)}`;
      })
      .join(" ");
  }, [ticks, yBase, t0, dt]);

  // Heatmap underlay
  const cells = useMemo(() => {
    if (!heatmap || !layers.heatmap) return null;
    const cellW = innerW / heatmap.buckets;
    const cellH = innerH / heatmap.levels;
    let max = 0;
    for (const row of heatmap.grid) for (const v of row) if (v > max) max = v;
    if (max <= 0) return null;
    const out: JSX.Element[] = [];
    for (let l = 0; l < heatmap.levels; l++) {
      for (let b = 0; b < heatmap.buckets; b++) {
        const v = heatmap.grid[l][b];
        if (v <= 0) continue;
        const op = Math.min(0.85, v / max);
        if (op < 0.04) continue;
        out.push(
          <rect
            key={`${l}-${b}`}
            x={M.left + b * cellW}
            y={M.top + innerH - (l + 1) * cellH}
            width={cellW}
            height={cellH}
            fill={`rgba(155,109,255,${op})`}
          />
        );
      }
    }
    return out;
  }, [heatmap, layers.heatmap, innerW, innerH]);

  // Bubbles
  const bubbleData = useMemo(() => {
    if (!layers.bubbles || trades.length === 0) return [];
    const sizes = trades.map((t) => t.price * t.size);
    const maxV = Math.max(...sizes, 1);
    return trades
      .map((tr) => {
        const tx = x(new Date(tr.t).getTime());
        if (tx < M.left - 5 || tx > M.left + innerW + 5) return null;
        const ty = yProb(tr.price);
        const $ = tr.price * tr.size;
        const r = Math.max(2.5, Math.min(14, 2.5 + Math.sqrt($ / maxV) * 14));
        const isYes = tr.outcome === "YES";
        const color = isYes ? "#22c55e" : "#ef4444";
        const filled = tr.side === "BUY";
        return { tx, ty, r, color, filled, tr };
      })
      .filter((b): b is NonNullable<typeof b> => b !== null);
  }, [trades, layers.bubbles, innerW, t0, dt]);

  // Volume bars
  const volBars = useMemo(() => {
    if (!layers.volume || trades.length === 0) return null;
    const buckets = 60;
    const bins = new Array<number>(buckets).fill(0);
    for (const tr of trades) {
      const p = (new Date(tr.t).getTime() - t0) / dt;
      if (p < 0 || p > 1) continue;
      const idx = Math.min(buckets - 1, Math.floor(p * buckets));
      bins[idx] += tr.price * tr.size;
    }
    const max = Math.max(...bins, 1);
    const w = innerW / buckets;
    return bins.map((v, i) => {
      if (v <= 0) return null;
      const h = (v / max) * (M.vol - 8);
      return (
        <rect
          key={i}
          x={M.left + i * w + 0.5}
          y={volTop + (M.vol - 8 - h) + 4}
          width={w - 1}
          height={h}
          fill="rgba(184,191,204,0.4)"
        />
      );
    });
  }, [trades, layers.volume, innerW, t0, dt, volTop]);

  // Time + price ticks
  const timeTicks = useMemo(() => {
    const out: { x: number; label: string }[] = [];
    for (let i = 0; i <= 5; i++) {
      const ms = t0 + (dt * i) / 5;
      const d = new Date(ms);
      out.push({ x: x(ms), label: pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes()) + ":" + pad(d.getUTCSeconds()) });
    }
    return out;
  }, [t0, dt]);

  const baseTicks = useMemo(() => {
    if (baseMin === baseMax) return [];
    return [0, 0.25, 0.5, 0.75, 1].map((p) => baseMin + (baseMax - baseMin) * p);
  }, [baseMin, baseMax]);

  // Hover state
  const [hover, setHover] = useState<Hover>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const onMove: React.MouseEventHandler<SVGSVGElement> = (e) => {
    const svg = svgRef.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    const local = pt.matrixTransform(ctm.inverse());
    if (local.x < M.left || local.x > M.left + innerW || local.y < M.top || local.y > M.top + innerH) {
      if (hover) setHover(null);
      return;
    }
    // Snap to nearest bubble within 14 px
    let best: { d: number; b: typeof bubbleData[0] } | null = null;
    for (const b of bubbleData) {
      const dx = b.tx - local.x;
      const dy = b.ty - local.y;
      const d = Math.sqrt(dx * dx + dy * dy);
      if (d <= b.r + 4 && (!best || d < best.d)) best = { d, b };
    }
    if (best) {
      setHover({ kind: "trade", x: best.b.tx, y: best.b.ty, trade: best.b.tr });
    } else {
      setHover({ kind: "cursor", x: local.x, y: local.y });
    }
  };
  const onLeave = () => setHover(null);

  const cursorTime = hover ? new Date(xInv(hover.x)) : null;
  const cursorProb = hover ? yProbInv(hover.y) : null;
  const cursorBase = hover && baseMin !== baseMax
    ? baseMin + (baseMax - baseMin) * (1 - (hover.y - M.top) / innerH)
    : null;

  return (
    <div style={{ position: "relative" }}>
      {/* Zoom toolbar */}
      <div className="anal-zoom">
        <button className="btn tiny ghost" onClick={zoomOut} title="Zoom out">−</button>
        <button className="btn tiny ghost" onClick={zoomReset} title="Reset zoom">RESET</button>
        <button className="btn tiny ghost" onClick={zoomIn} title="Zoom in">+</button>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${height}`}
        preserveAspectRatio="none"
        style={{ width: "100%", height, display: "block", background: "var(--bg-1)" }}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
      >
        {layers.heatmap && cells}

        {/* Probability gridlines + left axis */}
        {PROB_TICKS.map((p) => (
          <g key={p}>
            <line
              x1={M.left}
              x2={M.left + innerW}
              y1={yProb(p)}
              y2={yProb(p)}
              stroke="var(--line)"
              strokeDasharray={p === 0.5 ? "0" : "3 4"}
              opacity={p === 0.5 ? 0.6 : 0.5}
            />
            <text x={M.left - 8} y={yProb(p) + 3} fontSize="10" fontFamily="var(--font-mono)" fill="var(--fg-3)" textAnchor="end">
              {Math.round(p * 100)}¢
            </text>
          </g>
        ))}

        {/* Right axis BTC ticks */}
        {layers.base &&
          baseTicks.map((v, i) => (
            <text key={i} x={M.left + innerW + 8} y={yBase(v) + 3} fontSize="10" fontFamily="var(--font-mono)" fill="var(--fg-3)" textAnchor="start">
              ${formatBtc(v)}
            </text>
          ))}

        {/* Strike label on right axis (sits at y=50% by construction) */}
        {layers.strike && strike != null && (
          <text x={M.left + innerW + 8} y={yProb(0.5) - 4} fontSize="10" fontFamily="var(--font-mono)" fill="#fbbf24">
            ${formatBtc(strike)}
          </text>
        )}

        {/* Time axis */}
        <line x1={M.left} x2={M.left + innerW} y1={M.top + innerH} y2={M.top + innerH} stroke="var(--line-2)" />
        {timeTicks.map((t, i) => (
          <g key={i}>
            <line x1={t.x} x2={t.x} y1={M.top + innerH} y2={M.top + innerH + 4} stroke="var(--line-2)" />
            <text x={t.x} y={height - 8} fontSize="10" fontFamily="var(--font-mono)" fill="var(--fg-3)" textAnchor="middle">
              {t.label}
            </text>
          </g>
        ))}

        {/* Volume strip */}
        {layers.volume && (
          <>
            <rect x={M.left} y={volTop + 4} width={innerW} height={M.vol - 8} fill="rgba(15,20,28,0.6)" />
            {volBars}
            <text x={M.left - 8} y={volTop + M.vol / 2 + 3} fontSize="9" fontFamily="var(--font-mono)" fill="var(--fg-3)" textAnchor="end">
              VOL
            </text>
          </>
        )}

        {/* Base price line */}
        {layers.base && basePath && <path d={basePath} fill="none" stroke={baseColor} strokeWidth={1.5} opacity={0.85} />}

        {/* YES / NO lines (derived from trades) */}
        {layers.yes && yesPath && <path d={yesPath} fill="none" stroke="#22c55e" strokeWidth={1.5} />}
        {layers.no && noPath && <path d={noPath} fill="none" stroke="#ef4444" strokeWidth={1.5} />}

        {/* Bubbles */}
        {layers.bubbles &&
          bubbleData.map((b, i) => (
            <circle
              key={i}
              cx={b.tx}
              cy={b.ty}
              r={b.r}
              fill={b.filled ? b.color : "transparent"}
              stroke={b.color}
              strokeWidth={b.filled ? 0 : 1.4}
              opacity={0.7}
            />
          ))}

        {/* Crosshair */}
        {hover && (
          <>
            <line x1={hover.x} x2={hover.x} y1={M.top} y2={M.top + innerH} stroke="var(--line-3)" strokeDasharray="3 3" opacity={0.7} />
            <line x1={M.left} x2={M.left + innerW} y1={hover.y} y2={hover.y} stroke="var(--line-3)" strokeDasharray="3 3" opacity={0.7} />
            {/* Y axis labels at cursor */}
            {cursorProb != null && (
              <g>
                <rect x={M.left - 50} y={hover.y - 9} width={48} height={16} fill="var(--bg-3)" stroke="var(--line-3)" />
                <text x={M.left - 4} y={hover.y + 3} fontSize="10" fontFamily="var(--font-mono)" fill="var(--fg-0)" textAnchor="end">
                  {(cursorProb * 100).toFixed(1)}¢
                </text>
              </g>
            )}
            {cursorBase != null && (
              <g>
                <rect x={M.left + innerW + 2} y={hover.y - 9} width={56} height={16} fill="var(--bg-3)" stroke="var(--line-3)" />
                <text x={M.left + innerW + 8} y={hover.y + 3} fontSize="10" fontFamily="var(--font-mono)" fill="var(--fg-0)">
                  ${formatBtc(cursorBase)}
                </text>
              </g>
            )}
            {/* X axis label at cursor */}
            {cursorTime && (
              <g>
                <rect x={hover.x - 36} y={M.top + innerH + 2} width={72} height={16} fill="var(--bg-3)" stroke="var(--line-3)" />
                <text x={hover.x} y={M.top + innerH + 13} fontSize="10" fontFamily="var(--font-mono)" fill="var(--fg-0)" textAnchor="middle">
                  {fmtClock(cursorTime)}
                </text>
              </g>
            )}
          </>
        )}
      </svg>

      {/* Trade tooltip */}
      {hover && hover.kind === "trade" && (
        <div
          className="trade-tip"
          style={{
            position: "absolute",
            left: `${(hover.x / W) * 100}%`,
            top: `${(hover.y / height) * 100}%`,
            transform: "translate(12px, -50%)",
            pointerEvents: "none",
          }}
        >
          <div className="tt-row">
            <span className={hover.trade.outcome === "YES" ? "up" : "down"}>{hover.trade.outcome}</span>
            <span style={{ marginLeft: 6 }}>{hover.trade.side}</span>
          </div>
          <div className="tt-row mono">{(hover.trade.price * 100).toFixed(2)}¢ · ${(hover.trade.price * hover.trade.size).toFixed(2)}</div>
          <div className="tt-row dim mono">{fmtClock(new Date(hover.trade.t))}</div>
        </div>
      )}

      <style>{`
        .anal-zoom {
          position: absolute; top: 8px; right: 8px; z-index: 5;
          display: flex; gap: 4px; pointer-events: auto;
        }
        .anal-zoom .btn { min-width: 26px; }
        .trade-tip {
          background: var(--bg-3);
          border: 1px solid var(--line-3);
          padding: 6px 10px;
          font-family: var(--font-mono);
          font-size: 11px;
          border-radius: 3px;
          z-index: 10;
          box-shadow: 0 4px 12px rgba(0,0,0,0.5);
          white-space: nowrap;
        }
        .trade-tip .tt-row { display: block; }
        .trade-tip .tt-row.dim { color: var(--fg-3); font-size: 10px; }
      `}</style>
    </div>
  );
}

function makeLinePath(
  trades: Trade[],
  x: (ms: number) => number,
  y: (p: number) => number
): string {
  if (trades.length === 0) return "";
  // Step path: each trade defines a price level that holds until the next trade.
  let d = "";
  let prevX: number | null = null;
  let prevY: number | null = null;
  for (let i = 0; i < trades.length; i++) {
    const t = trades[i];
    const cx = x(new Date(t.t).getTime());
    const cy = y(t.price);
    if (i === 0) {
      d += `M ${cx.toFixed(1)} ${cy.toFixed(1)}`;
    } else {
      // step horizontally to new x, then vertical to new y
      d += ` L ${cx.toFixed(1)} ${prevY!.toFixed(1)} L ${cx.toFixed(1)} ${cy.toFixed(1)}`;
    }
    prevX = cx;
    prevY = cy;
  }
  return d;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}
function formatBtc(v: number): string {
  if (v >= 1000) return Math.round(v).toLocaleString();
  return v.toFixed(2);
}
function fmtClock(d: Date): string {
  return pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes()) + ":" + pad(d.getUTCSeconds()) + " UTC";
}
