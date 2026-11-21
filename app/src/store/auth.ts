// Sesión del usuario: inicio con usuario + PIN de 4 dígitos contra el servidor del puesto de
// mando, y respaldo SIN CONEXIÓN para quien ya entró antes en este teléfono (un socorrista en
// campo solo ve el Wi-Fi del albergue, no el servidor).
//
// Para el respaldo se guarda en el teléfono un PBKDF2 del PIN con sal propia (nunca el PIN ni
// el hash del servidor). Con 4 dígitos no es una protección fuerte si alguien roba el teléfono;
// solo evita que cualquiera que lo tome entre sin saber el PIN.
import { create } from "zustand";
import { HttpError, ServerClient, type Role, type UserInfo } from "../lib/server";
import { load, now, save } from "../lib/util";

export interface Session extends UserInfo {
  token?: string;     // sin token = sesión sin conexión (no puede usar el servidor hasta reconectar)
  expira: number;
  serverUrl: string;
  offline: boolean;
}

interface CachedCredential {
  usuario: string;
  nombre: string;
  rol: Role;
  equipo?: string | null;
  salt: string;
  hash: string;
}

interface AuthState {
  session?: Session;
  guest: boolean;
  serverUrl: string;
  lastUser: string;
  login: (usuario: string, pin: string, serverUrl: string) => Promise<Session>;
  enterAsGuest: () => void;
  logout: () => Promise<void>;
  changePin: (actual: string, nuevo: string) => Promise<void>;
  client: () => ServerClient | undefined;
}

const SESSION_SECS = 12 * 3600;
const DEFAULT_URL = "http://192.168.137.1:8080";

const toHex = (b: ArrayBuffer | Uint8Array) =>
  Array.from(b instanceof Uint8Array ? b : new Uint8Array(b), (x) => x.toString(16).padStart(2, "0")).join("");

async function pinHash(pin: string, saltHex: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(pin), "PBKDF2", false, ["deriveBits"]);
  const salt = new Uint8Array(saltHex.match(/../g)!.map((h) => parseInt(h, 16)));
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: 100_000 }, key, 256);
  return toHex(bits);
}

async function cacheCredential(u: UserInfo, pin: string) {
  const salt = toHex(crypto.getRandomValues(new Uint8Array(16)));
  const creds = load<Record<string, CachedCredential>>("credenciales", {});
  creds[u.usuario] = { usuario: u.usuario, nombre: u.nombre, rol: u.rol, equipo: u.equipo, salt,
                       hash: await pinHash(pin, salt) };
  save("credenciales", creds);
}

async function offlineLogin(usuario: string, pin: string): Promise<CachedCredential | undefined> {
  const c = load<Record<string, CachedCredential>>("credenciales", {})[usuario];
  if (!c) return undefined;
  return (await pinHash(pin, c.salt)) === c.hash ? c : undefined;
}

function restoreSession(): Session | undefined {
  const s = load<Session | null>("sesion", null);
  return s && s.expira > now() ? s : undefined;
}

export const useAuth = create<AuthState>()((set, get) => ({
  session: restoreSession(),
  guest: false,
  serverUrl: load("servidor.url", load("mando.url", DEFAULT_URL)),
  lastUser: load("ultimoUsuario", ""),

  login: async (usuarioRaw, pin, serverUrl) => {
    const usuario = usuarioRaw.trim().toLowerCase();
    save("servidor.url", serverUrl);
    save("ultimoUsuario", usuario);
    set({ serverUrl, lastUser: usuario });
    let session: Session;
    try {
      const r = await new ServerClient(serverUrl).login(usuario, pin);
      session = { ...r, serverUrl, offline: false };
      await cacheCredential(r, pin);
    } catch (e) {
      if (e instanceof HttpError) throw e; // PIN incorrecto, bloqueado…: no usar el respaldo
      // Sin conexión con el servidor: probar con la credencial guardada en este teléfono.
      const c = await offlineLogin(usuario, pin);
      if (!c) {
        const known = !!load<Record<string, CachedCredential>>("credenciales", {})[usuario];
        throw new Error(known
          ? "PIN incorrecto"
          : "No hay conexión con el puesto de mando. La primera vez debes entrar conectado a su Wi‑Fi.");
      }
      session = { usuario: c.usuario, nombre: c.nombre, rol: c.rol, equipo: c.equipo, expira: now() + SESSION_SECS,
                  serverUrl, offline: true };
    }
    save("sesion", session);
    set({ session, guest: false });
    return session;
  },

  enterAsGuest: () => set({ guest: true, session: undefined }),

  logout: async () => {
    const c = get().client();
    if (c) await c.logout().catch(() => {});
    save("sesion", null);
    set({ session: undefined, guest: false });
  },

  changePin: async (actual, nuevo) => {
    const s = get().session;
    const c = get().client();
    if (!s || !c) throw new Error("Necesitas conexión con el puesto de mando para cambiar el PIN");
    await c.changePin(actual, nuevo);
    await cacheCredential(s, nuevo);
    const updated = { ...s, pin_inicial: 0 };
    save("sesion", updated);
    set({ session: updated });
  },

  client: () => {
    const s = get().session;
    return s?.token ? new ServerClient(s.serverUrl, s.token) : undefined;
  },
}));

export const ROLE_LABEL: Record<Role, string> = {
  admin: "Administrador",
  mando: "Puesto de mando",
  socorrista: "Socorrista",
};
