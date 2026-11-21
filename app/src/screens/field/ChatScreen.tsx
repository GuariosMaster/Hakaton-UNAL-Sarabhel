import { useEffect, useRef } from "react";
import { Composer, Empty, PriorityBadge } from "../../components/ui";
import { ago } from "../../lib/util";
import { nodeLabel, useField } from "../../store/field";

const STATUS_ICON = { enviando: "⏳", "en-red": "✓", entregado: "✓✓", fallo: "⚠" } as const;

export function FieldChatScreen() {
  const { messages, nodes, myNum, status, send } = useField();
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  const destinations = [
    { id: "^all", label: "Todos (canal general)" },
    ...Object.values(nodes)
      .filter((n) => n.num !== myNum)
      .map((n) => ({ id: n.id, label: n.longName ?? n.id })),
  ];

  return (
    <div className="screen chat">
      <div className="chat-list">
        {messages.length === 0 && <Empty>Aún no hay mensajes. Lo que llegue por la red de radio aparecerá aquí.</Empty>}
        {messages.map((m) => (
          <div key={m.key} className={`bubble ${m.mine ? "mine" : ""} ${m.priority}`}>
            <div className="meta">
              <b>{m.mine ? `Yo → ${nodeLabel(nodes, m.to)}` : nodeLabel(nodes, m.from)}</b>
              {m.priority !== "informativo" && <PriorityBadge p={m.priority} />}
            </div>
            <div className="text">{m.text}</div>
            <div className="meta small">
              <span>{ago(m.ts)}</span>
              {m.mine && m.status && <span title={m.status}>{STATUS_ICON[m.status]}</span>}
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
      <Composer destinations={destinations} disabled={status !== "conectado"} onSend={(t, to) => send(t, to)} />
    </div>
  );
}
