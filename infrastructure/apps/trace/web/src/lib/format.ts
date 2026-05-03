export function fmt(n: number | null | undefined, d = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function fmtCompact(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(2) + "K";
  return n.toFixed(0);
}

export function fmtPct(n: number, d = 2): string {
  return (n >= 0 ? "+" : "") + n.toFixed(d) + "%";
}

export function fmtTime(t: string | number | Date): string {
  return new Date(t).toTimeString().slice(0, 8);
}

export function fmtWindowTime(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    pad(s.getUTCMonth() + 1) +
    "/" +
    pad(s.getUTCDate()) +
    " " +
    pad(s.getUTCHours()) +
    ":" +
    pad(s.getUTCMinutes()) +
    "–" +
    pad(e.getUTCHours()) +
    ":" +
    pad(e.getUTCMinutes())
  );
}

export function localTZ(): string {
  const offset = -new Date().getTimezoneOffset() / 60;
  return "UTC" + (offset >= 0 ? "+" : "") + offset;
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}
