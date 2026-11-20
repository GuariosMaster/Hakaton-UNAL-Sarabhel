// Misma clasificación que el servidor (server/sarabhel/priority.py) para que
// la app y el puesto de mando muestren la misma prioridad.

export type Priority = "critico" | "moderado" | "informativo";

const CRITICAL = [
  "sos", "auxilio", "socorro", "emergencia", "urgente",
  "herid\\w*", "atrapad\\w*", "sangr\\w*", "fractur\\w*", "inconscient\\w*",
  "no respira", "infarto", "incendi\\w*", "fuego", "explosi\\w*",
  "derrumb\\w*", "colaps\\w*", "escombros?", "sepultad\\w*", "deslizamiento",
  "(fuga|olor) a gas", "muert[oa]s?", "desaparecid\\w*",
];
const MODERATE = [
  "agua", "comida", "aliment\\w*", "medicina\\w*", "medicament\\w*", "insulina",
  "refugio", "albergue", "evacu\\w*", "grietas?", "cobijas?", "frio",
  "bateria\\w*", "bebes?", "embarazada", "ayuda", "necesit\\w*", "bloquead\\w*",
];

const build = (words: string[]) => new RegExp(`\\b(?:${words.join("|")})\\b`);
const RE_CRITICAL = build(CRITICAL);
const RE_MODERATE = build(MODERATE);

export const normalize = (t: string) =>
  t.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");

export function classify(text: string): Priority {
  const t = normalize(text);
  if (RE_CRITICAL.test(t)) return "critico";
  if (RE_MODERATE.test(t)) return "moderado";
  return "informativo";
}

/** Mensajes rápidos del botón de emergencia (coinciden con canned_messages de los nodos). */
export const QUICK_MESSAGES: { label: string; text: string; icon: string }[] = [
  { icon: "🩸", label: "Herido", text: "SOS Herido" },
  { icon: "🧱", label: "Atrapado", text: "SOS Atrapado" },
  { icon: "🔥", label: "Incendio", text: "SOS Incendio" },
  { icon: "💧", label: "Necesito agua", text: "Necesito agua" },
  { icon: "💊", label: "Necesito medicina", text: "Necesito medicina" },
  { icon: "🏃", label: "Evacuando", text: "Evacuando" },
  { icon: "✅", label: "Estoy bien", text: "Estoy bien" },
];
