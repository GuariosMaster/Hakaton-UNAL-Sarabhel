import { useEffect, useState } from "react";
import { BottomNav, Header, Pill, type Tab } from "./components/ui";
import {
  CommandAlertsScreen, CommandChatScreen, CommandMapScreen, CommandSettingsScreen, type Focus,
} from "./screens/command/CommandScreens";
import { FieldChatScreen } from "./screens/field/ChatScreen";
import { ConnectScreen } from "./screens/field/ConnectScreen";
import { FieldMapScreen } from "./screens/field/MapScreen";
import { SosScreen } from "./screens/field/SosScreen";
import { useCommand } from "./store/command";
import { useField } from "./store/field";
import { load, save } from "./lib/util";

type Mode = "campo" | "mando";

export default function App() {
  const [mode, setMode] = useState<Mode | null>(() => load<Mode | null>("modo", null));
  const choose = (m: Mode | null) => {
    save("modo", m);
    setMode(m);
  };
  if (mode === "campo") return <FieldApp onChangeMode={() => choose("mando")} />;
  if (mode === "mando") return <CommandApp onChangeMode={() => choose("campo")} />;
  return <ModeSelect onChoose={choose} />;
}

function ModeSelect({ onChoose }: { onChoose: (m: Mode) => void }) {
  return (
    <div className="mode-select">
      <div className="brand">
        <div className="logo">📡</div>
        <h1>Red de Emergencia LoRa</h1>
        <p className="muted">Comunicación sin internet ni señal celular</p>
      </div>
      <button type="button" className="mode-card" onClick={() => onChoose("campo")}>
        <span className="icon">🧑‍🚒</span>
        <span><b>Estoy en campo</b><br /><small>Conecto mi nodo LoRa por Bluetooth para pedir ayuda y enviar mensajes</small></span>
      </button>
      <button type="button" className="mode-card" onClick={() => onChoose("mando")}>
        <span className="icon">🗺️</span>
        <span><b>Puesto de mando</b><br /><small>Veo el mapa, las alertas y los mensajes de toda la red desde el servidor local</small></span>
      </button>
    </div>
  );
}

type FieldTab = "sos" | "chat" | "mapa" | "conexion";

function FieldApp({ onChangeMode }: { onChangeMode: () => void }) {
  const [tab, setTab] = useState<FieldTab>("sos");
  const { status, nodes, myNum, kind } = useField();
  const me = myNum != null ? nodes[myNum] : undefined;
  const tone = status === "conectado" ? "ok" : status === "desconectado" ? "off" : "warn";
  const label = status === "conectado"
    ? `${kind === "bluetooth" ? me?.shortName ?? "Nodo" : "Demo"}${me?.battery != null ? ` · ${me.battery}%` : ""}`
    : status === "desconectado" ? "Sin nodo" : "Conectando…";

  const tabs: Tab<FieldTab>[] = [
    { id: "sos", label: "SOS", icon: "🆘" },
    { id: "chat", label: "Mensajes", icon: "💬" },
    { id: "mapa", label: "Mapa", icon: "🗺️" },
    { id: "conexion", label: "Conexión", icon: "📶" },
  ];
  const titles: Record<FieldTab, string> = { sos: "Emergencia", chat: "Mensajes", mapa: "Mapa", conexion: "Conexión" };

  return (
    <div className="app">
      <Header title={titles[tab]} right={<Pill tone={tone} onClick={() => setTab("conexion")}>{label}</Pill>} />
      <main>
        {tab === "sos" && <SosScreen />}
        {tab === "chat" && <FieldChatScreen />}
        {tab === "mapa" && <FieldMapScreen />}
        {tab === "conexion" && <ConnectScreen onChangeMode={onChangeMode} />}
      </main>
      <BottomNav tabs={tabs} active={tab} onChange={setTab} />
    </div>
  );
}

type CommandTab = "alertas" | "mapa" | "chat" | "ajustes";

function CommandApp({ onChangeMode }: { onChangeMode: () => void }) {
  const { status, alerts, url, connect } = useCommand();
  const [tab, setTab] = useState<CommandTab>(status === "conectado" ? "alertas" : "ajustes");
  const [focus, setFocus] = useState<Focus>();
  const [seen, setSeen] = useState(0);

  // Intentar reconectar al servidor guardado al abrir la app.
  useEffect(() => {
    if (useCommand.getState().status === "desconectado") void connect(url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (tab === "alertas") setSeen(alerts.length);
  }, [tab, alerts.length]);

  const tone = status === "conectado" ? "ok" : status === "conectando" ? "warn" : "off";
  const tabs: Tab<CommandTab>[] = [
    { id: "alertas", label: "Alertas", icon: "🚨", badge: Math.max(0, alerts.length - seen) },
    { id: "mapa", label: "Mapa", icon: "🗺️" },
    { id: "chat", label: "Mensajes", icon: "💬" },
    { id: "ajustes", label: "Servidor", icon: "⚙️" },
  ];
  const titles: Record<CommandTab, string> = { alertas: "Alertas", mapa: "Mapa de la red", chat: "Mensajes", ajustes: "Servidor" };

  return (
    <div className="app">
      <Header title={titles[tab]} right={
        <Pill tone={tone} onClick={() => setTab("ajustes")}>
          {status === "conectado" ? "En vivo" : status === "conectando" ? "Conectando…" : "Sin servidor"}
        </Pill>
      } />
      <main>
        {tab === "alertas" && (
          <CommandAlertsScreen onLocate={(lat, lon) => { setFocus({ lat, lon, seq: Date.now() }); setTab("mapa"); }} />
        )}
        {tab === "mapa" && <CommandMapScreen focus={focus} />}
        {tab === "chat" && <CommandChatScreen />}
        {tab === "ajustes" && <CommandSettingsScreen onChangeMode={onChangeMode} />}
      </main>
      <BottomNav tabs={tabs} active={tab} onChange={setTab} />
    </div>
  );
}
