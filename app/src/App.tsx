import { useEffect, useState } from "react";
import { BottomNav, Header, Pill, type Tab } from "./components/ui";
import { load, save } from "./lib/util";
import { UsersScreen } from "./screens/AccountScreen";
import {
  CommandAlertsScreen, CommandChatScreen, CommandEnergyScreen, CommandMapScreen, CommandSettingsScreen, type Focus,
} from "./screens/command/CommandScreens";
import { AssignedScreen } from "./screens/field/AssignedScreen";
import { FieldChatScreen } from "./screens/field/ChatScreen";
import { ConnectScreen } from "./screens/field/ConnectScreen";
import { FieldMapScreen } from "./screens/field/MapScreen";
import { SosScreen } from "./screens/field/SosScreen";
import { LoginScreen } from "./screens/LoginScreen";
import { useAuth } from "./store/auth";
import { useCommand } from "./store/command";
import { useField } from "./store/field";

type Mode = "campo" | "mando";

/**
 * Qué ve cada quien:
 *  - Sin cuenta (emergencia): modo Campo con SOS, mensajes y mapa. Nunca se bloquea pedir ayuda.
 *  - Socorrista: modo Campo + "Asignadas" (alertas de su equipo).
 *  - Puesto de mando: modo Mando (y puede pasar a Campo).
 *  - Administrador: lo mismo que Mando + administración de usuarios.
 */
export default function App() {
  const { session, guest } = useAuth();
  const [mode, setMode] = useState<Mode>(() => load<Mode>("modo", "mando"));
  const choose = (m: Mode) => {
    save("modo", m);
    setMode(m);
  };

  if (!session && !guest) return <LoginScreen />;
  if (!session || session.rol === "socorrista") return <FieldApp />;
  return mode === "campo"
    ? <FieldApp onChangeMode={() => choose("mando")} />
    : <CommandApp onChangeMode={() => choose("campo")} />;
}

type FieldTab = "sos" | "chat" | "mapa" | "asignadas" | "conexion";

function FieldApp({ onChangeMode }: { onChangeMode?: () => void }) {
  const [tab, setTab] = useState<FieldTab>("sos");
  const { status, nodes, myNum, kind, autoConnect, locate, messages } = useField();
  const session = useAuth((s) => s.session);
  const me = myNum != null ? nodes[myNum] : undefined;
  const queued = messages.filter((m) => m.mine && m.status === "en-cola").length;

  // Al abrir: reconectar a la última red usada y tomar la ubicación GPS para que el SOS sea inmediato.
  useEffect(() => {
    autoConnect();
    void locate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tone = status === "conectado" ? "ok" : status === "desconectado" ? "off" : "warn";
  const label = status === "conectado"
    ? `${kind === "simulador" ? "Demo" : kind === "red-local" ? "Puesto" : me?.shortName ?? me?.longName?.slice(0, 10) ?? "Albergue"}${kind !== "red-local" && me?.battery != null ? ` · 🔋${me.battery}%` : ""}`
    : status === "desconectado" ? (queued ? `Sin conexión · ${queued} en cola` : "Sin conexión") : "Conectando…";

  const tabs: Tab<FieldTab>[] = [
    { id: "sos", label: "SOS", icon: "🆘" },
    { id: "chat", label: "Mensajes", icon: "💬", badge: queued || undefined },
    { id: "mapa", label: "Mapa", icon: "🗺️" },
    ...(session?.rol === "socorrista" ? [{ id: "asignadas" as const, label: "Asignadas", icon: "🚑" }] : []),
    { id: "conexion", label: session ? "Cuenta" : "Conexión", icon: session ? "👤" : "📶" },
  ];
  const titles: Record<FieldTab, string> = {
    sos: "Emergencia", chat: "Mensajes", mapa: "Mapa", asignadas: "Alertas de mi equipo", conexion: session ? "Conexión y cuenta" : "Conexión",
  };

  return (
    <div className="app">
      <Header title={titles[tab]} right={<Pill tone={tone} onClick={() => setTab("conexion")}>{label}</Pill>} />
      <main>
        {tab === "sos" && <SosScreen />}
        {tab === "chat" && <FieldChatScreen />}
        {tab === "mapa" && <FieldMapScreen />}
        {tab === "asignadas" && <AssignedScreen />}
        {tab === "conexion" && <ConnectScreen onChangeMode={onChangeMode} />}
      </main>
      <BottomNav tabs={tabs} active={tab} onChange={setTab} />
    </div>
  );
}

type CommandTab = "alertas" | "mapa" | "chat" | "energia" | "ajustes" | "usuarios";

function CommandApp({ onChangeMode }: { onChangeMode: () => void }) {
  const { status, alerts, connect } = useCommand();
  const session = useAuth((s) => s.session);
  const [tab, setTab] = useState<CommandTab>("alertas");
  const [focus, setFocus] = useState<Focus>();

  // Conectar al servidor de la sesión al abrir.
  useEffect(() => {
    if (session && useCommand.getState().status === "desconectado") void connect(session.serverUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tone = status === "conectado" ? "ok" : status === "conectando" ? "warn" : "off";
  const pending = alerts.filter((a) => a.estado === "nueva").length;
  const tabs: Tab<CommandTab>[] = [
    { id: "alertas", label: "Alertas", icon: "🚨", badge: pending },
    { id: "mapa", label: "Mapa", icon: "🗺️" },
    { id: "chat", label: "Mensajes", icon: "💬" },
    { id: "energia", label: "Energía", icon: "🔋" },
    { id: "ajustes", label: "Ajustes", icon: "⚙️" },
  ];
  const titles: Record<CommandTab, string> = {
    alertas: "Alertas", mapa: "Mapa de la red", chat: "Mensajes", energia: "Energía", ajustes: "Ajustes", usuarios: "Usuarios",
  };

  return (
    <div className="app">
      <Header title={titles[tab]} right={
        <Pill tone={tone} onClick={() => setTab("ajustes")}>
          {status === "conectado" ? "En vivo" : status === "conectando" ? "Conectando…" : "Sin servidor"}
        </Pill>
      } />
      {status === "error" && tab !== "ajustes" && (
        <button type="button" className="banner" onClick={() => setTab("ajustes")}>
          ⚠ Sin conexión con el servidor. Toca para revisar.
        </button>
      )}
      <main>
        {tab === "alertas" && (
          <CommandAlertsScreen onLocate={(lat, lon) => { setFocus({ lat, lon, seq: Date.now() }); setTab("mapa"); }} />
        )}
        {tab === "mapa" && <CommandMapScreen focus={focus} />}
        {tab === "chat" && <CommandChatScreen />}
        {tab === "energia" && <CommandEnergyScreen />}
        {tab === "ajustes" && (
          <CommandSettingsScreen onChangeMode={onChangeMode}
                                 onUsers={session?.rol === "admin" ? () => setTab("usuarios") : undefined} />
        )}
        {tab === "usuarios" && <UsersScreen onBack={() => setTab("ajustes")} />}
      </main>
      <BottomNav tabs={tabs} active={tab === "usuarios" ? "ajustes" : tab} onChange={setTab} />
    </div>
  );
}
