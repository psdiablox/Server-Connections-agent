import { useMemo } from "react";
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

const M = { left: 56, right: 64, top: 16, bottom: 28, vol: 56 }; // chart margins
const PROB_TICKS = [0, 0.2, 0.4, 0.5, 0.6, 0.8, 1];

export function AnalysisChart({
  ticks,
  trades,
  heatmap,
  startsAt,
  endsAt,
  strike,
  baseColor,
  layers,
  height = 520,
}: Props) {
  const W = 1200;
  const H = height;
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom - (layers.volume ? M.vol : 0);
  const volTop = M.top + innerH;

  const t0 = new Date(startsAt).getTime();
  const t1 = new Date(endsAt).getTime();
  const dt = Math.max(1, t1 - t0);

  const x = (ms: number) => M.left + ((ms - t0) / dt) * innerW;
  const yProb = (p: number) => M.top + (1 - p) * innerH;

  // Base price scale
  const { yBase, baseMin, baseMax } = useMemo(() => {
    const bases = ticks.map((t) => t.base_price).filter((v): v is number => v != null);
    if (strike != null) bases.push(strike);
    if (bases.length === 0) {
      const mid = strike ?? 0;
      return { yBase: () => M.top + innerH / 2, baseMin: mid, baseMax: mid };
    }
    let mn = Math.min(...bases), mx = Math.max(...bases);
    if (mn === mx) {
      mn = mn * 0.999;
      mx = mx * 1.001;
    } else {
      const pad = (mx - mn) * 0.15;
      mn -= pad;
      mx += pad;
    }
    return {
      yBase: (v: number) => M.top + (1 - (v - mn) / (mx - mn)) * innerH,
      baseMin: mn,
      baseMax: mx,
    };
  }, [ticks, strike, innerH]);

  // Probability lines
  const yesPath = useMemo(() => makePath(ticks, "yes", x, yProb), [ticks]);
  const noPath = useMemo(() => makePath(ticks, "no", x, yProb), [ticks]);
  const basePath = useMemo(
    () =>
      ticks
        .filter((t) => t.base_price != null)
        .map((t, i) => `${i === 0 ? "M" : "L"} ${x(new Date(t.t).getTime()).toFixed(1)} ${yBase(t.base_price!).toFixed(1)}`)
        .join(" "),
    [ticks, yBase]
  );

  // Heatmap cells
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
        const opacity = Math.min(0.85, v / max);
        if (opacity < 0.04) continue;
        out.push(
          <rect
            key={`${l}-${b}`}
            x={M.left + b * cellW}
            y={M.top + innerH - (l + 1) * cellH}
            width={cellW}
            height={cellH}
            fill={`rgba(155, 109, 255, ${opacity})`}
          />
        );
      }
    }
    return out;
  }, [heatmap, layers.heatmap, innerW, innerH]);

  // Trade bubbles — filled circle for BUY, ring for SELL.
  const bubbles = useMemo(() => {
    if (!layers.bubbles || trades.length === 0) return null;
    const sizes = trades.map((t) => t.price * t.size);
    const maxV = Math.max(...sizes, 1);
    return trades.map((tr, i) => {
      const tx = x(new Date(tr.t).getTime());
      if (tx < M.left || tx > M.left + innerW) return null;
      const ty = yProb(tr.price);
      const $ = tr.price * tr.size;
      const r = Math.max(2.5, Math.min(14, 2.5 + Math.sqrt($ / maxV) * 14));
      const isYes = tr.outcome === "YES";
      const color = isYes ? "#22c55e" : "#ef4444";
      const filled = tr.side === "BUY";
      return (
        <circle
          key={i}
          cx={tx}
          cy={ty}
          r={r}
          fill={filled ? color : "transparent"}
          stroke={color}
          strokeWidth={filled ? 0 : 1.4}
          opacity={0.7}
        />
      );
    });
  }, [trades, layers.bubbles, innerW]);

  // Volume bars: bucket trades into 60 columns across the window.
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
          fill="rgba(184, 191, 204, 0.4)"
        />
      );
    });
  }, [trades, layers.volume, innerW, t0, dt, volTop]);

  // Time axis: 6 ticks across the window
  const timeTicks = useMemo(() => {
    const out: { x: number; label: string }[] = [];
    for (let i = 0; i <= 5; i++) {
      const ms = t0 + (dt * i) / 5;
      const d = new Date(ms);
      const label = pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes());
      out.push({ x: x(ms), label });
    }
    return out;
  }, [t0, dt]);

  // Right axis ticks — base price
  const baseTicks = useMemo(() => {
    if (baseMin === baseMax) return [];
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((p) => baseMin + (baseMax - baseMin) * p);
    return ticks;
  }, [baseMin, baseMax]);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height: H, display: "block", background: "var(--bg-1)" }}
    >
      {/* Heatmap underlay */}
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
          <text
            x={M.left - 8}
            y={yProb(p) + 3}
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill="var(--fg-3)"
            textAnchor="end"
          >
            {Math.round(p * 100)}¢
          </text>
        </g>
      ))}

      {/* Right axis (BTC price) */}
      {layers.base &&
        baseTicks.map((v, i) => (
          <text
            key={i}
            x={M.left + innerW + 8}
            y={yBase(v) + 3}
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill="var(--fg-3)"
            textAnchor="start"
          >
            ${formatBtc(v)}
          </text>
        ))}

      {/* Strike line — horizontal at strike on PRICE axis */}
      {layers.strike && strike != null && (
        <>
          <line
            x1={M.left}
            x2={M.left + innerW}
            y1={yBase(strike)}
            y2={yBase(strike)}
            stroke="#fbbf24"
            strokeWidth={1}
            strokeDasharray="6 4"
            opacity={0.7}
          />
          <text
            x={M.left + innerW + 8}
            y={yBase(strike) - 4}
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill="#fbbf24"
          >
            ${formatBtc(strike)}
          </text>
        </>
      )}

      {/* Time axis */}
      <line
        x1={M.left}
        x2={M.left + innerW}
        y1={M.top + innerH}
        y2={M.top + innerH}
        stroke="var(--line-2)"
      />
      {timeTicks.map((t, i) => (
        <g key={i}>
          <line x1={t.x} x2={t.x} y1={M.top + innerH} y2={M.top + innerH + 4} stroke="var(--line-2)" />
          <text
            x={t.x}
            y={H - 8}
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill="var(--fg-3)"
            textAnchor="middle"
          >
            {t.label}
          </text>
        </g>
      ))}

      {/* Volume strip (bottom) */}
      {layers.volume && (
        <>
          <rect x={M.left} y={volTop + 4} width={innerW} height={M.vol - 8} fill="rgba(15,20,28,0.6)" />
          {volBars}
          <text
            x={M.left - 8}
            y={volTop + M.vol / 2 + 3}
            fontSize="9"
            fontFamily="var(--font-mono)"
            fill="var(--fg-3)"
            textAnchor="end"
          >
            VOL
          </text>
        </>
      )}

      {/* Base price line */}
      {layers.base && basePath && <path d={basePath} fill="none" stroke={baseColor} strokeWidth={1.5} opacity={0.85} />}

      {/* YES / NO probability lines */}
      {layers.yes && yesPath && <path d={yesPath} fill="none" stroke="#22c55e" strokeWidth={1.6} />}
      {layers.no && noPath && <path d={noPath} fill="none" stroke="#ef4444" strokeWidth={1.6} />}

      {/* Trade bubbles on top */}
      {layers.bubbles && bubbles}
    </svg>
  );
}

function makePath(
  ticks: Tick[],
  key: "yes" | "no",
  x: (ms: number) => number,
  y: (p: number) => number
): string {
  const pts = ticks.filter((t) => t[key] != null);
  if (pts.length === 0) return "";
  return pts.map((t, i) => `${i === 0 ? "M" : "L"} ${x(new Date(t.t).getTime()).toFixed(1)} ${y(t[key]!).toFixed(1)}`).join(" ");
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function formatBtc(v: number): string {
  if (v >= 1000) return Math.round(v).toLocaleString();
  return v.toFixed(2);
}
