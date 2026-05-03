import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, HttpError, type Coin, type Network, type WindowSummary } from "./api";
import { Login } from "./screens/Login";
import { Networks } from "./screens/Networks";
import { PolyCoins } from "./screens/PolyCoins";
import { PolyWindows } from "./screens/PolyWindows";
import { PolyAnalysis } from "./screens/PolyAnalysis";
import { EmptyState } from "./screens/EmptyState";

type AuthState = { ready: boolean; user: string | null };

function useAuth(): [AuthState, (u: string | null) => void] {
  const [state, setState] = useState<AuthState>({ ready: false, user: null });
  useEffect(() => {
    api
      .me()
      .then((m) => setState({ ready: true, user: m.username }))
      .catch((err) => {
        if (!(err instanceof HttpError) || err.status !== 401) console.error("auth check failed", err);
        setState({ ready: true, user: null });
      });
  }, []);
  const setUser = (u: string | null) => setState({ ready: true, user: u });
  return [state, setUser];
}

function AuthGate({ user }: { user: string | null }) {
  const loc = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />;
  return <Outlet />;
}

function NetworkRoute() {
  const { slug } = useParams();
  const [net, setNet] = useState<Network | null>(null);
  const [err, setErr] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!slug) return;
    api.network(slug).then(setNet).catch(() => setErr(true));
  }, [slug]);

  if (err) return <EmptyState
    network={{ slug: slug || "", name: slug || "", kind: "?", enabled: false, sort_order: 0, meta: {} }}
    onHome={() => navigate("/")}
    message="// network not found"
    subtitle="" />;
  if (!net) return <div className="grid-bg" style={{ height: "100vh" }} />;
  if (!net.enabled)
    return <EmptyState network={net} onHome={() => navigate("/")} message="// no data yet for this network" subtitle="The collector only ingests Polymarket → BTC 5-min markets in this build." />;
  if (net.kind === "prediction")
    return <PolyCoins network={net} onBack={() => navigate("/")} onPick={(c) => navigate(`/networks/${net.slug}/${c.slug}`)} />;
  return <EmptyState network={net} onHome={() => navigate("/")} message="// no data yet for this network" subtitle="" />;
}

function CoinRoute() {
  const { slug, coin: coinSlug } = useParams();
  const [net, setNet] = useState<Network | null>(null);
  const [coin, setCoin] = useState<Coin | null>(null);
  const [err, setErr] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!slug || !coinSlug) return;
    Promise.all([api.network(slug), api.networkCoins(slug)])
      .then(([n, coins]) => {
        setNet(n);
        const c = coins.find((x) => x.slug === coinSlug);
        if (!c) setErr(true);
        else setCoin(c);
      })
      .catch(() => setErr(true));
  }, [slug, coinSlug]);

  if (err && net) return <EmptyState network={net} onHome={() => navigate("/")} onBack={() => navigate(`/networks/${net.slug}`)} message="// coin not found in this network" subtitle="" />;
  if (!net || !coin) return <div className="grid-bg" style={{ height: "100vh" }} />;
  if (!coin.enabled)
    return <EmptyState
      network={net}
      coin={coin}
      onHome={() => navigate("/")}
      onBack={() => navigate(`/networks/${net.slug}`)}
      message="// no data yet for this coin"
      subtitle="Only BTC 5-min windows are being collected for now." />;
  return <PolyWindows
    network={net}
    coin={coin}
    onHome={() => navigate("/")}
    onBack={() => navigate(`/networks/${net.slug}`)}
    onPick={(w) => navigate(`/markets/${w.id}`)} />;
}

function MarketRoute() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<{ net: Network; coin: Coin; window: WindowSummary } | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    const mid = Number(id);
    if (!mid) {
      setErr(true);
      return;
    }
    api
      .market(mid)
      .then(async (m) => {
        const net = await api.network(m.network_slug);
        const coins = await api.networkCoins(m.network_slug);
        const coin = coins.find((c) => c.slug === m.coin_slug);
        if (!coin) throw new Error("coin missing");
        const window: WindowSummary = {
          id: m.id, external_id: m.external_id,
          starts_at: m.starts_at!, ends_at: m.ends_at!,
          period_seconds: m.period_seconds || 300,
          strike: m.strike, status: m.status, resolution: m.resolution,
          total_volume: m.total_volume, traders: m.traders,
          last_yes: m.last_yes, last_no: m.last_no,
          trade_count: null, largest_trade: null, avg_trade: null, close_btc: null,
          data_coverage_pct: null,
        };
        setData({ net, coin, window });
      })
      .catch(() => setErr(true));
  }, [id]);

  if (err) return <div className="grid-bg" style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
    <div className="panel" style={{ padding: 16 }}>
      <div className="mono" style={{ color: "var(--down)" }}>// market not found</div>
      <button className="btn ghost sm" style={{ marginTop: 12 }} onClick={() => navigate("/")}>NETWORKS</button>
    </div>
  </div>;
  if (!data) return <div className="grid-bg" style={{ height: "100vh" }} />;
  return <PolyAnalysis
    network={data.net}
    coin={data.coin}
    window={data.window}
    onHome={() => navigate("/")}
    onBack={(where) =>
      where === "coins"
        ? navigate(`/networks/${data.net.slug}`)
        : navigate(`/networks/${data.net.slug}/${data.coin.slug}`)
    }
    onNavigateToMarket={(mid) => navigate(`/markets/${mid}`)} />;
}

function NetworksRoute({ user, onLogout }: { user: string; onLogout: () => void }) {
  const navigate = useNavigate();
  return <Networks
    user={user}
    onPick={(n) => navigate(`/networks/${n.slug}`)}
    onLogout={async () => { onLogout(); }} />;
}

export function App() {
  const [auth, setUser] = useAuth();

  useEffect(() => {
    document.body.style.overscrollBehavior = "none";
  }, []);

  if (!auth.ready) return <div className="grid-bg" style={{ height: "100vh" }} />;

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={<LoginRoute user={auth.user} onLogin={(u) => setUser(u)} />}
        />
        <Route element={<AuthGate user={auth.user} />}>
          <Route
            path="/"
            element={<NetworksRoute user={auth.user || ""} onLogout={async () => { await api.logout().catch(() => {}); setUser(null); }} />}
          />
          <Route path="/networks/:slug" element={<NetworkRoute />} />
          <Route path="/networks/:slug/:coin" element={<CoinRoute />} />
          <Route path="/markets/:id" element={<MarketRoute />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function LoginRoute({ user, onLogin }: { user: string | null; onLogin: (u: string) => void }) {
  const loc = useLocation();
  const navigate = useNavigate();
  if (user) return <Navigate to="/" replace />;
  const from = (loc.state as { from?: string } | null)?.from || "/";
  return <Login onLogin={(u) => { onLogin(u); navigate(from, { replace: true }); }} />;
}
