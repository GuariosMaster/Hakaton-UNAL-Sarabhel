import { useEffect, useState } from "react";
import { Empty } from "../components/ui";
import type { Role, UserInfo } from "../lib/server";
import { ROLE_LABEL, useAuth } from "../store/auth";

/** Mi cuenta: datos, cambio de PIN y salir. */
export function AccountCard() {
  const { session, changePin, logout } = useAuth();
  const [open, setOpen] = useState(!!session?.pin_inicial);
  const [actual, setActual] = useState("");
  const [nuevo, setNuevo] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string }>();
  if (!session) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await changePin(actual, nuevo);
      setMsg({ ok: true, text: "PIN actualizado" });
      setActual("");
      setNuevo("");
      setOpen(false);
    } catch (ex) {
      setMsg({ ok: false, text: ex instanceof Error ? ex.message : String(ex) });
    }
  }

  return (
    <div className={`card ${session.pin_inicial ? "warn" : ""}`}>
      <p><b>👤 {session.nombre}</b> · {ROLE_LABEL[session.rol]}{session.equipo ? ` · ${session.equipo}` : ""}</p>
      <p className="muted">
        Usuario {session.usuario}
        {session.offline ? " · sesión sin conexión (algunas funciones necesitan el puesto de mando)" : ""}
      </p>
      {session.pin_inicial ? <p><b>Cambia el PIN que te asignaron.</b></p> : null}
      {open ? (
        <form className="lan-form" onSubmit={submit}>
          <label className="field">PIN actual
            <input value={actual} onChange={(e) => setActual(e.target.value.replace(/\D/g, ""))}
                   inputMode="numeric" maxLength={4} type="password" required />
          </label>
          <label className="field">PIN nuevo (4 dígitos)
            <input value={nuevo} onChange={(e) => setNuevo(e.target.value.replace(/\D/g, ""))}
                   inputMode="numeric" maxLength={4} type="password" required />
          </label>
          <div className="row">
            <button type="button" onClick={() => setOpen(false)}>Cancelar</button>
            <button type="submit" className="primary" disabled={actual.length !== 4 || nuevo.length !== 4}>Guardar PIN</button>
          </div>
        </form>
      ) : (
        <div className="row">
          <button type="button" onClick={() => { setOpen(true); setMsg(undefined); }}>🔑 Cambiar PIN</button>
          <button type="button" onClick={() => void logout()}>Salir</button>
        </div>
      )}
      {msg && <p className={msg.ok ? "ok" : "error"}>{msg.text}</p>}
    </div>
  );
}

const EMPTY = { usuario: "", nombre: "", rol: "socorrista" as Role, equipo: "", pin: "" };

/** Administración de usuarios (solo rol admin; necesita conexión con el servidor). */
export function UsersScreen({ onBack }: { onBack: () => void }) {
  const client = useAuth((s) => s.client)();
  const me = useAuth((s) => s.session?.usuario);
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string>();

  async function reload() {
    if (!client) return;
    try {
      setUsers(await client.users());
      setError(undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void reload(); }, []);

  async function run(fn: () => Promise<unknown>) {
    try {
      await fn();
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!client) {
    return <div className="screen"><Empty>Para administrar usuarios entra conectado al puesto de mando.</Empty></div>;
  }

  return (
    <div className="screen">
      <button type="button" className="link" onClick={onBack}>← Volver</button>
      <h2>Usuarios ({users.length})</h2>
      {error && <p className="error">{error}</p>}
      <ul className="list">
        {users.map((u) => (
          <li key={u.usuario} className={u.activo ? "" : "inactivo"}>
            <div className="meta">
              <b>{u.nombre} <span className="muted">({u.usuario})</span></b>
              <span>{ROLE_LABEL[u.rol]}</span>
            </div>
            <div className="meta">
              <span>{u.equipo ? `👥 ${u.equipo}` : "Sin equipo"}{u.activo ? "" : " · desactivado"}</span>
              {u.pin_inicial ? <span>PIN inicial</span> : null}
            </div>
            <div className="acciones">
              <button type="button" className="mini" onClick={() => {
                const p = prompt(`Nuevo PIN para ${u.usuario} (4 dígitos):`);
                if (p) void run(() => client.updateUser(u.usuario, { pin: p }));
              }}>PIN</button>
              <button type="button" className="mini" onClick={() => {
                const v = prompt("Equipo:", u.equipo ?? "");
                if (v !== null) void run(() => client.updateUser(u.usuario, { equipo: v }));
              }}>Equipo</button>
              {u.usuario !== me && (
                <>
                  <select className="mini" value={u.rol} aria-label="Rol"
                          onChange={(e) => void run(() => client.updateUser(u.usuario, { rol: e.target.value as Role }))}>
                    {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                  </select>
                  <button type="button" className="mini"
                          onClick={() => void run(() => client.updateUser(u.usuario, { activo: !u.activo }))}>
                    {u.activo ? "Desactivar" : "Activar"}
                  </button>
                  <button type="button" className="mini" onClick={() => {
                    if (confirm(`¿Eliminar a ${u.usuario}? No se puede deshacer.`)) void run(() => client.deleteUser(u.usuario));
                  }}>Eliminar</button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>

      <h2>Nuevo usuario</h2>
      <form className="card" onSubmit={(e) => {
        e.preventDefault();
        void run(async () => {
          await client.createUser({ ...form, usuario: form.usuario.trim().toLowerCase(), equipo: form.equipo || null });
          setForm(EMPTY);
        });
      }}>
        <label className="field">Usuario
          <input value={form.usuario} onChange={(e) => setForm({ ...form, usuario: e.target.value })}
                 autoCapitalize="off" placeholder="ej. ana.perez" required />
        </label>
        <label className="field">Nombre
          <input value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} required />
        </label>
        <label className="field">Rol
          <select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value as Role })}>
            {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </select>
        </label>
        <label className="field">Equipo (para socorristas)
          <input value={form.equipo} onChange={(e) => setForm({ ...form, equipo: e.target.value })} placeholder="ej. Bomberos 2" />
        </label>
        <label className="field">PIN inicial (4 dígitos)
          <input value={form.pin} onChange={(e) => setForm({ ...form, pin: e.target.value.replace(/\D/g, "") })}
                 inputMode="numeric" maxLength={4} required />
        </label>
        <button type="submit" className="primary" disabled={form.pin.length !== 4}>Crear usuario</button>
        <p className="muted">La persona debe cambiar el PIN inicial al entrar por primera vez.</p>
      </form>
    </div>
  );
}
