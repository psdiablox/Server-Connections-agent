import { useState } from "react";
import { api, HttpError } from "../api";

export function Login({ onLogin }: { onLogin: (username: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const m = await api.login(username, password);
      onLogin(m.username);
    } catch (e) {
      setErr(e instanceof HttpError && e.status === 401 ? "invalid credentials" : "login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid-bg" style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="frame-top" style={{ position: "fixed", top: 0, left: 0, right: 0 }}>
        <div className="brand"><span className="dot">●</span>TRACE TERMINAL</div>
        <div className="crumb"><span className="cur">SIGN IN</span></div>
      </div>

      <form className="panel" onSubmit={submit} style={{ width: 380, padding: 0 }}>
        <div className="panel-head"><span className="title">SECURE ACCESS</span></div>
        <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <div className="label" style={{ marginBottom: 6 }}>USERNAME</div>
            <input
              className="input"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div>
            <div className="label" style={{ marginBottom: 6 }}>PASSWORD</div>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {err && <div className="mono" style={{ color: "var(--down)", fontSize: 11 }}>{err}</div>}
          <button className="btn primary" disabled={busy} style={{ marginTop: 4, height: 36 }}>
            {busy ? "…" : "SIGN IN"}
          </button>
          <div className="tiny" style={{ marginTop: 8, lineHeight: 1.6 }}>
            Two-layer auth — your IP is already whitelisted at the proxy.
            This adds a credential gate on top.
          </div>
        </div>
      </form>

      <div className="frame-bottom" style={{ position: "fixed", bottom: 0, left: 0, right: 0 }}>
        <span className="seg"><span className="dot"></span>GATEWAY</span>
        <span className="spacer"></span>
        <span><span className="kbd">↵</span> sign in</span>
      </div>
    </div>
  );
}
