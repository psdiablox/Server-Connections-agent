// Thin fetch wrapper. Cookies are httpOnly so we just rely on `credentials: include`.

export type Network = {
  slug: string;
  name: string;
  kind: string;
  color?: string;
  tagline?: string;
  enabled: boolean;
  sort_order: number;
  meta: Record<string, unknown>;
};

export type Coin = {
  slug: string;
  symbol: string;
  name: string;
  color?: string;
  base_price?: number | null;
  enabled: boolean;
  meta: Record<string, unknown>;
};

export type Timeframe = { id: string; label: string; seconds: number };

export type WindowSummary = {
  id: number;
  external_id: string;
  starts_at: string;
  ends_at: string;
  period_seconds: number;
  strike: number | null;
  status: "upcoming" | "live" | "ended";
  resolution: "YES" | "NO" | null;
  total_volume: number | null;
  traders: number | null;
  last_yes: number | null;
  last_no: number | null;
  trade_count: number | null;
  largest_trade: number | null;
  avg_trade: number | null;
  close_btc: number | null;
};

export type WindowList = {
  items: WindowSummary[];
  total: number;
  counts: Record<string, number>;
};

export type Outcome = { id: number; label: string; external_token_id: string | null };

export type Market = WindowSummary & {
  network_slug: string;
  coin_slug: string | null;
  kind: string;
  question: string | null;
  resolved_at: string | null;
  outcomes: Outcome[];
};

export type Tick = { t: string; base_price: number | null; yes: number | null; no: number | null };

export type Trade = { t: string; outcome: string; side: "BUY" | "SELL"; price: number; size: number };

export type Heatmap = {
  levels: number;
  buckets: number;
  starts_at: string;
  ends_at: string;
  grid: number[][];
};

export type Outage = {
  source: string;
  start: string;
  end: string;
  reason: string | null;
  duration_seconds: number;
};

export type OrderStats = {
  yes_buy_count: number;
  yes_sell_count: number;
  no_buy_count: number;
  no_sell_count: number;
  yes_buy_volume: number;
  yes_sell_volume: number;
  no_buy_volume: number;
  no_sell_volume: number;
  largest_trade: number | null;
  avg_trade: number | null;
};

const BASE = "/api";

class HttpError extends Error {
  status: number;
  constructor(status: number, msg: string) {
    super(msg);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new HttpError(r.status, text || r.statusText);
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export const api = {
  // auth
  login: (username: string, password: string) =>
    req<{ username: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => req<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => req<{ username: string }>("/auth/me"),

  // catalogue
  networks: () => req<Network[]>("/networks"),
  network: (slug: string) => req<Network>(`/networks/${slug}`),
  networkCoins: (slug: string) => req<Coin[]>(`/networks/${slug}/coins`),
  timeframes: (network: string, coin: string) =>
    req<Timeframe[]>(`/networks/${network}/coins/${coin}/timeframes`),
  windows: (
    network: string,
    coin: string,
    params: { tf?: string; status?: string; resolution?: string; sort?: string; dir?: "asc" | "desc"; limit?: number; offset?: number } = {}
  ) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)));
    return req<WindowList>(`/networks/${network}/coins/${coin}/windows?${q}`);
  },

  // markets
  market: (id: number) => req<Market>(`/markets/${id}`),
  ticks: (id: number, bucket = 5) => req<Tick[]>(`/markets/${id}/ticks?bucket=${bucket}`),
  trades: (id: number, limit = 2000) => req<Trade[]>(`/markets/${id}/trades?limit=${limit}`),
  heatmap: (id: number, levels = 80, buckets = 80, outcome = "YES") =>
    req<Heatmap>(`/markets/${id}/book/heatmap?levels=${levels}&buckets=${buckets}&outcome=${outcome}`),
  orderStats: (id: number) => req<OrderStats>(`/markets/${id}/order-stats`),
  outages: (id: number) => req<Outage[]>(`/markets/${id}/outages`),
};

export { HttpError };
