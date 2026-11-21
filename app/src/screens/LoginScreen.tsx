import { useState } from "react";
import { PinPad } from "../components/PinPad";
import { useAuth } from "../store/auth";

export function LoginScreen() {
  const { login, enterAsGuest, lastUser, serverUrl } = useAuth();
  const [usuario, setUsuario] = useState(lastUser);
  const [url, setUrl] = useState(serverUrl);
  const [showServer, setShowServer] = useState(false);
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
    <div className="login">
      <div className="brand">
        <div className="logo">📡</div>
        <h1>Red de Emergencia</h1>
        <p className="muted">Comunicación sin internet ni señal celular</p>
      </div>

      <button type="button" className="sos-guest" onClick={enterAsGuest}>
        🆘 Emergencia — pedir ayuda sin cuenta
      </button>

      <div className="card login-card">
        <label className="field">Usuario
          <input value={usuario} onChange={(e) => setUsuario(e.target.value)} autoCapitalize="off"
                 autoComplete="username" placeholder="ej. ana.perez" />
        </label>
        <p className="muted center">PIN de 4 dígitos</p>
        <PinPad onComplete={(pin) => void submit(pin)} error={error ? `${errorSeq}` : undefined} busy={busy} />
        {busy && <p className="muted center">Verificando…</p>}
        {error && <p className="error center">{error}</p>}
        <button type="button" className="link" onClick={() => setShowServer((v) => !v)}>
          ⚙️ Servidor del puesto de mando
        </button>
        {showServer && (
          <label className="field">Dirección
            <input value={url} onChange={(e) => setUrl(e.target.value)} inputMode="url" autoCapitalize="off" />
          </label>
        )}
      </div>
    </div>
  );
}
