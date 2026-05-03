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

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

// "MAY 04, 15:55-16:00" in UTC — kept for breadcrumb / data-feed contexts.
export function fmtWindowTime(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    MONTHS[s.getUTCMonth()] +
    " " +
    pad(s.getUTCDate()) +
    ", " +
    pad(s.getUTCHours()) +
    ":" +
    pad(s.getUTCMinutes()) +
    "–" +
    pad(e.getUTCHours()) +
    ":" +
    pad(e.getUTCMinutes())
  );
}

// "MAY 04, 11:55-12:00" in America/New_York — matches Polymarket's own label.
export function fmtWindowET(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const dateFmt = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    month: "short",
    day: "2-digit",
  });
  const timeFmt = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return (
    dateFmt.format(s).toUpperCase().replace(" ", " ") +
    ", " +
    timeFmt.format(s) +
    "–" +
    timeFmt.format(e)
  );
}

export function fmtLocalWindow(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const pad = (n: number) => String(n).padStart(2, "0");
  const today = new Date();
  const sameDay =
    s.getFullYear() === today.getFullYear() &&
    s.getMonth() === today.getMonth() &&
    s.getDate() === today.getDate();
  const datePart = sameDay
    ? ""
    : MONTHS[s.getMonth()] + " " + pad(s.getDate()) + ", ";
  return (
    datePart +
    pad(s.getHours()) + ":" + pad(s.getMinutes()) +
    "–" +
    pad(e.getHours()) + ":" + pad(e.getMinutes())
  );
}

export function localTZ(): string {
  const offset = -new Date().getTimezoneOffset() / 60;
  return "UTC" + (offset >= 0 ? "+" : "") + offset;
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}
