import { useEffect, useState } from "react";
import { api, HttpError, type Coin, type Network, type WindowSummary } from "./api";
import { Login } from "./screens/Login";
import { Networks } from "./screens/Networks";
import { PolyCoins } from "./screens/PolyCoins";
import { PolyWindows } from "./screens/PolyWindows";
import { PolyAnalysis } from "./screens/PolyAnalysis";
import { EmptyState } from "./screens/EmptyState";

type Route =
  | { name: "login" }
  | { name: "networks" }
  | { name: "polyCoins"; network: Network }
  | { name: "polyWindows"; network: Network; coin: Coin }
  | { name: "polyAnalysis"; network: Network; coin: Coin; window: WindowSummary }
  | { name: "emptyMarkets"; network: Network }
  | { name: "emptyWindows"; network: Network; coin: Coin };

export function App() {
  const [route, setRoute] = useState<Route>({ name: "login" });
  const [user, setUser] = useState<string | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);

  useEffect(() => {
    document.body.style.overscrollBehavior = "none";
    api
      .me()
      .then((m) => {
        setUser(m.username);
        setRoute({ name: "networks" });
      })
      .catch((err) => {
        if (!(err instanceof HttpError) || err.status !== 401) {
          console.error("auth check failed", err);
        }
      })
      .finally(() => setBootstrapping(false));
  }, []);

  if (bootstrapping) return <div className="grid-bg" style={{ height: "100vh" }} />;

  switch (route.name) {
    case "login":
      return (
        <Login
          onLogin={(u) => {
            setUser(u);
            setRoute({ name: "networks" });
          }}
        />
      );
    case "networks":
      return (
        <Networks
          user={user!}
          onPick={(n) => {
            if (!n.enabled) return setRoute({ name: "emptyMarkets", network: n });
            if (n.kind === "prediction") return setRoute({ name: "polyCoins", network: n });
            return setRoute({ name: "emptyMarkets", network: n });
          }}
          onLogout={async () => {
            await api.logout().catch(() => {});
            setUser(null);
            setRoute({ name: "login" });
          }}
        />
      );
    case "polyCoins":
      return (
        <PolyCoins
          network={route.network}
          onBack={() => setRoute({ name: "networks" })}
          onPick={(c) => {
            if (!c.enabled) return setRoute({ name: "emptyWindows", network: route.network, coin: c });
            return setRoute({ name: "polyWindows", network: route.network, coin: c });
          }}
        />
      );
    case "polyWindows":
      return (
        <PolyWindows
          network={route.network}
          coin={route.coin}
          onHome={() => setRoute({ name: "networks" })}
          onBack={() => setRoute({ name: "polyCoins", network: route.network })}
          onPick={(w) => setRoute({ name: "polyAnalysis", network: route.network, coin: route.coin, window: w })}
        />
      );
    case "polyAnalysis":
      return (
        <PolyAnalysis
          network={route.network}
          coin={route.coin}
          window={route.window}
          onHome={() => setRoute({ name: "networks" })}
          onBack={(where) =>
            where === "coins"
              ? setRoute({ name: "polyCoins", network: route.network })
              : setRoute({ name: "polyWindows", network: route.network, coin: route.coin })
          }
        />
      );
    case "emptyMarkets":
      return (
        <EmptyState
          network={route.network}
          onHome={() => setRoute({ name: "networks" })}
          message="// no data yet for this network"
          subtitle="The collector only ingests Polymarket → BTC 5-min markets in this build."
        />
      );
    case "emptyWindows":
      return (
        <EmptyState
          network={route.network}
          coin={route.coin}
          onHome={() => setRoute({ name: "networks" })}
          onBack={() => setRoute({ name: "polyCoins", network: route.network })}
          message="// no data yet for this coin"
          subtitle="Only BTC 5-min windows are being collected for now."
        />
      );
  }
}
