import { useEffect, useState } from "react";
import { PinPad } from "../components/PinPad";
import { ServerClient } from "../lib/server";
import { useAuth } from "../store/auth";

type View = "entrar" | "registro";

export function LoginScreen() {
  const { serverUrl, lastUser } = useAuth();
  const [view, setView] = useState<View>(lastUser ? "entrar" : "registro");
  const [url, setUrl] = useState(serverUrl);
  const [showServer, setShowServer] = useState(false);
  const [estado, setEstado] = useState<{ registro: boolean; admin_inicial: boolean } | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);

  // ¿Hay servidor? ¿Está abierto el registro? ¿Es el primer uso (admin con PIN inicial)?
  useEffect(() => {
    let alive = true;
    setOnline(null);
    const t = setTimeout(() => {
      new ServerClient(url).authStatus()
        .then((e) => { if (alive) { setEstado(e); setOnline(true); } })
        .catch(() => { if (alive) { setEstado(null); setOnline(false); } });
    }, 400);
    return () => { alive = false; clearTimeout(t); };
  }, [url]);

  return (
    <div className="login">
      <div className="brand">
        <div className="logo">📡</div>
        <h1>Red de Emergencia</h1>
        <p className="muted">Comunicación sin internet ni señal celular</p>
      </div>

      <button type="button" className="sos-guest" onClick={useAuth.getState().enterAsGuest}>
        🆘 Emergencia — pedir ayuda sin cuenta
      </button>

      <div className="card login-card">
        <div className="segmented" role="tablist">
          <button type="button" role="tab" aria-selected={view === "entrar"} className={view === "entrar" ? "on" : ""}
                  onClick={() => setView("entrar")}>Entrar</button>
          <button type="button" role="tab" aria-selected={view === "registro"} className={view === "registro" ? "on" : ""}
                  onClick={() => setView("registro")}>Crear cuenta</button>
        </div>

        {estado?.admin_inicial && view === "entrar" && (
          <p className="hint">Primer uso: entra como <b>admin</b> con el PIN <b>1234</b> y cámbialo.</p>
        )}

        {view === "entrar" ? <LoginForm url={url} /> : <RegisterForm url={url} estado={estado} onDone={() => setView("entrar")} />}

        <div className="server-line">
          <span className={`dot ${online ? "ok" : online === false ? "off" : ""}`} />
          <span className="muted">
            {online ? "Puesto de mando conectado" : online === false ? "Sin conexión con el puesto de mando" : "Buscando el puesto de mando…"}
          </span>
          <button type="button" className="link" onClick={() => setShowServer((v) => !v)}>⚙️</button>
        </div>
        {showServer && (
          <label className="field">Dirección del servidor
            <input value={url} onChange={(e) => setUrl(e.target.value)} inputMode="url" autoCapitalize="off" />
          </label>
        )}
      </div>
    </div>
  );
}

function LoginForm({ url }: { url: string }) {
  const { login, lastUser } = useAuth();
  const [usuario, setUsuario] = useState(lastUser);
  const [error, setError] = useState<string>();
  const [errorSeq, setErrorSeq] = useState(0);
  const [busy, setBusy] = useState(false);

  async function submit(pin: string) {
    if (!usuario.trim()) {
      setError("Escribe tu usuario");
      setErrorSeq((n) => n + 1);
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      await login(usuario, pin, url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setErrorSeq((n) => n + 1);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <label className="field">Usuario
        <input value={usuario} onChange={(e) => setUsuario(e.target.value)} autoCapitalize="off"
               autoComplete="username" placeholder="ej. ana.perez" />
      </label>
      <p className="muted center">PIN de 4 dígitos</p>
      <PinPad onComplete={(pin) => void submit(pin)} error={error ? `${errorSeq}` : undefined} busy={busy} />
      {busy && <p className="muted center">Verificando…</p>}
      {error && <p className="error center">{error}</p>}
    </>
  );
}

function RegisterForm({ url, estado, onDone }: {
  url: string;
  estado: { registro: boolean } | null;
  onDone: () => void;
}) {
  const register = useAuth((s) => s.register);
  const [usuario, setUsuario] = useState("");
  const [pin, setPin] = useState("");
  const [pin2, setPin2] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const usuarioOk = /^[a-z0-9._-]{3,20}$/.test(usuario.trim().toLowerCase());
  const pinsOk = /^\d{4}$/.test(pin) && pin === pin2;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!pinsOk) {
      setError(pin !== pin2 ? "Los dos PIN no coinciden" : "El PIN debe tener 4 dígitos");
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      const u = usuario.trim().toLowerCase();
      await register({ usuario: u, nombre: u, pin }, url);
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  if (estado && !estado.registro) {
    return (
      <div className="hint">
        El registro está cerrado en este puesto de mando: pide tu cuenta al administrador.
        <button type="button" className="link" onClick={onDone}>Ya tengo cuenta</button>
      </div>
    );
  }

  return (
    <form className="register" onSubmit={submit}>
      <label className="field">Usuario
        <input value={usuario} onChange={(e) => setUsuario(e.target.value.toLowerCase())} autoCapitalize="off"
               autoComplete="username" required maxLength={20} placeholder="ej. socorrista1" />
        {usuario && !usuarioOk && <small className="error">3 a 20 caracteres: letras, números, punto o guion</small>}
      </label>
      <div className="row">
        <label className="field">PIN (4 dígitos)
          <input value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))} type="password"
                 inputMode="numeric" autoComplete="new-password" required />
        </label>
        <label className="field">Repite el PIN
          <input value={pin2} onChange={(e) => setPin2(e.target.value.replace(/\D/g, "").slice(0, 4))} type="password"
                 inputMode="numeric" autoComplete="new-password" required />
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      <button type="submit" className="primary" disabled={busy || !usuarioOk || !pinsOk}>
        {busy ? "Creando…" : "Crear cuenta y entrar"}
      </button>
      <p className="muted small-print">
        Las cuentas nuevas son de <b>socorrista</b>.
      </p>
    </form>
  );
}
