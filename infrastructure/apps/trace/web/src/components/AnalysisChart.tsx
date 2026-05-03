import { useMemo } from "react";
import type { Heatmap, Tick } from "../api";

export type ChartLayers = {
  yes: boolean;
  no: boolean;
  base: boolean;
  strike: boolean;
  heatmap: boolean;
};

export function AnalysisChart({
  ticks,
  heatmap,
  strike,
  baseColor,
  layers,
  height = 520,
}: {
  ticks: Tick[];
  heatmap: Heatmap | null;
  strike: number | null;
  baseColor: string;
  layers: ChartLayers;
  height?: number;
}) {
  const w = 1000;
  const h = height;

  const { yesPath, noPath, basePath, baseRange, t0, t1 } = useMemo(() => {
    if (ticks.length < 2) return { yesPath: "", noPath: "", basePath: "", baseRange: [0, 1], t0: 0, t1: 1 };
    const t0 = new Date(ticks[0].t).getTime();
    const t1 = new Date(ticks[ticks.length - 1].t).getTime();
    const dt = t1 - t0 || 1;
    const x = (t: string) => ((new Date(t).getTime() - t0) / dt) * w;

    // yes/no on [0..1]
    const yp = ticks
      .filter((t) => t.yes != null)
      .map((t, i) => `${i === 0 ? "M" : "L"} ${x(t.t).toFixed(1)} ${(h - (t.yes! * h)).toFixed(1)}`)
      .join(" ");
    const np = ticks
      .filter((t) => t.no != null)
      .map((t, i) => `${i === 0 ? "M" : "L"} ${x(t.t).toFixed(1)} ${(h - (t.no! * h)).toFixed(1)}`)
      .join(" ");

    // base price scaled to its own range
    const bases = ticks.map((t) => t.base_price).filter((v): v is number => v != null);
    let bMin = Math.min(...bases), bMax = Math.max(...bases);
    if (!isFinite(bMin) || !isFinite(bMax) || bMin === bMax) {
      bMin = strike ? strike * 0.99 : 0;
      bMax = strike ? strike * 1.01 : 1;
    }
    const padPct = 0.1;
    bMin = bMin - (bMax - bMin) * padPct;
    bMax = bMax + (bMax - bMin) * padPct;
    const yBase = (v: number) => h - ((v - bMin) / (bMax - bMin)) * h;
    const bp = ticks
      .filter((t) => t.base_price != null)
      .map((t, i) => `${i === 0 ? "M" : "L"} ${x(t.t).toFixed(1)} ${yBase(t.base_price!).toFixed(1)}`)
      .join(" ");

    return { yesPath: yp, noPath: np, basePath: bp, baseRange: [bMin, bMax], t0, t1 };
  }, [ticks, h, strike]);

  // Heatmap: paint as cells, faded purple
  const cells = useMemo(() => {
    if (!heatmap || !layers.heatmap) return null;
    const cellW = w / heatmap.buckets;
    const cellH = h / heatmap.levels;
    let max = 0;
    for (const row of heatmap.grid) for (const v of row) if (v > max) max = v;
    if (max <= 0) return null;
    const out: JSX.Element[] = [];
    for (let l = 0; l < heatmap.levels; l++) {
      for (let b = 0; b < heatmap.buckets; b++) {
        const v = heatmap.grid[l][b];
        if (v <= 0) continue;
        const opacity = Math.min(0.9, v / max);
        if (opacity < 0.05) continue;
        out.push(
          <rect
            key={`${l}-${b}`}
            x={b * cellW}
            y={h - (l + 1) * cellH}
            width={cellW}
            height={cellH}
            fill={`rgba(155, 109, 255, ${opacity})`}
          />
        );
      }
    }
    return out;
  }, [heatmap, layers.heatmap, h]);

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height: h, display: "block", background: "var(--bg-1)" }}
    >
      {/* gridlines */}
      {[0, 0.25, 0.5, 0.75, 1].map((p, i) => (
        <line key={i} x1={0} x2={w} y1={h - p * h} y2={h - p * h} stroke="var(--line)" strokeDasharray="3 4" />
      ))}

      {layers.heatmap && cells}

      {layers.strike && strike != null && (
        // 50¢ line in probability space
        <line x1={0} x2={w} y1={h * 0.5} y2={h * 0.5} stroke="#fbbf24" strokeWidth={1} strokeDasharray="6 4" />
      )}

      {layers.base && basePath && (
        <path d={basePath} fill="none" stroke={baseColor} strokeWidth={1.5} />
      )}

      {layers.yes && yesPath && <path d={yesPath} fill="none" stroke="#22c55e" strokeWidth={1.5} />}
      {layers.no && noPath && <path d={noPath} fill="none" stroke="#ef4444" strokeWidth={1.5} />}
    </svg>
  );
}
