// Nodo de albergue: ESP32 + RFM69HCW + micro-red solar.
//
// - Crea una red Wi-Fi abierta "Emergencia <nombre>" con portal cautivo: cualquier teléfono que
//   se conecte ve la página para enviar reportes, sin instalar nada y sin internet.
// - Expone una API HTTP para la app móvil (modo Campo, conexión "Wi-Fi del albergue").
// - Envía los reportes por radio FSK (RHMesh) al gateway del puesto de mando, con la energía
//   del nodo en cada trama, y reporta telemetría cada 5 minutos.
// - Reenvía tramas de otros nodos (malla multi-salto).
#include <ArduinoJson.h>
#include <DNSServer.h>
#include <WebServer.h>
#include <WiFi.h>

#include "portal.h"
#include "red.h"

RH_RF69 radio(PIN_RF_CS, PIN_RF_INT);
RHMesh mesh(radio, NODE_ADDRESS);
WebServer server(80);
DNSServer dns;

// --- Mensajes recientes (para el portal y la app) ------------------------------
struct Mensaje {
  uint32_t seq;
  uint8_t de;
  uint8_t para;
  bool propio;          // enviado desde este nodo
  unsigned long t;      // millis() al recibir/enviar
  char texto[MAX_TEXTO_LARGO + 1];
};
static const int MAX_MENSAJES = 30;
static Mensaje mensajes[MAX_MENSAJES];
static int totalMensajes = 0;
static uint32_t seq = 0;

static Energia energia = {0, 0, 0};
static unsigned long ultimoTel = 0, ultimoInfo = 0, ultimaMedicion = 0;
static uint8_t buf[MAX_PAQUETE + 8];
static Reensamblador reensamblador;
static char textoLargo[MAX_TEXTO_LARGO + 1];

static void guardarMensaje(uint8_t de, uint8_t para, const char* texto, bool propio) {
  Mensaje& m = mensajes[totalMensajes % MAX_MENSAJES];
  m.seq = ++seq;
  m.de = de;
  m.para = para;
  m.propio = propio;
  m.t = millis();
  strncpy(m.texto, texto, sizeof(m.texto) - 1);
  m.texto[sizeof(m.texto) - 1] = 0;
  totalMensajes++;
}

static uint8_t enviarTrama(const char* tipo, const char* msg, uint8_t dest = GATEWAY_ADDRESS) {
  char trama[MAX_PAQUETE + 1];
  size_t n = armarTrama(trama, sizeof(trama), tipo, energia.bat, energia.panel, energia.carga, msg);
  return mesh.sendtoWait((uint8_t*)trama, n, dest);
}

static size_t bytesUtf8(const char* s) { return strlen(s); }

// --- HTTP ----------------------------------------------------------------------
static void cabecerasCors() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

static void responderJson(int code, JsonDocument& doc) {
  String out;
  serializeJson(doc, out);
  cabecerasCors();
  server.send(code, "application/json", out);
}

static void apiEstado() {
  JsonDocument doc;
  doc["nodo"] = NODE_ADDRESS;
  doc["nombre"] = NODE_NAME;
  doc["bat"] = energia.bat;
  doc["panel"] = energia.panel;
  doc["carga"] = energia.carga;
  doc["conectados"] = WiFi.softAPgetStationNum();
  doc["max_texto"] = MAX_TEXTO_LARGO;
  doc["uptime"] = millis() / 1000;
  responderJson(200, doc);
}

static void apiMensajes() {
  uint32_t desde = server.hasArg("desde") ? strtoul(server.arg("desde").c_str(), nullptr, 10) : 0;
  JsonDocument doc;
  doc["ultimo"] = seq;
  JsonArray arr = doc["mensajes"].to<JsonArray>();
  int inicio = totalMensajes > MAX_MENSAJES ? totalMensajes - MAX_MENSAJES : 0;
  for (int i = inicio; i < totalMensajes; i++) {
    const Mensaje& m = mensajes[i % MAX_MENSAJES];
    if (m.seq <= desde) continue;
    JsonObject o = arr.add<JsonObject>();
    o["seq"] = m.seq;
    o["de"] = m.de;
    o["para"] = m.para;
    o["propio"] = m.propio;
    o["hace"] = (millis() - m.t) / 1000;
    o["msg"] = m.texto;
  }
  responderJson(200, doc);
}

// POST /api/mensaje  {"tipo":"texto","mensaje":"SOS Atrapado","destino":1,"latitud":5.06,"longitud":-75.50}
static void apiEnviar() {
  JsonDocument in, out;
  if (deserializeJson(in, server.arg("plain"))) {
    out["ok"] = false;
    out["error"] = "JSON inválido";
    return responderJson(400, out);
  }
  const char* msg = in["mensaje"] | in["cuerpo"] | in["msg"] | "";
  int dest = in["destino"] | in["dest"] | (int)GATEWAY_ADDRESS;
  if (!msg[0] || bytesUtf8(msg) > MAX_TEXTO_LARGO) {
    out["ok"] = false;
    out["error"] = "El mensaje debe tener entre 1 y " + String(MAX_TEXTO_LARGO) + " bytes";
    return responderJson(400, out);
  }
  if (dest < 1 || dest > 254) dest = GATEWAY_ADDRESS;

  // Ubicación del teléfono (si la envió la app): trama POS antes del mensaje.
  double lat = 0.0, lon = 0.0;
  bool tienePos = false;
  if (!in["latitud"].isNull() && !in["longitud"].isNull()) {
    lat = in["latitud"].as<double>();
    lon = in["longitud"].as<double>();
    tienePos = true;
  } else if (!in["lat"].isNull() && !in["lon"].isNull()) {
    lat = in["lat"].as<double>();
    lon = in["lon"].as<double>();
    tienePos = true;
  }

  if (tienePos) {
    char pos[32];
    snprintf(pos, sizeof(pos), "%.5f,%.5f", lat, lon);
    enviarTrama("POS", pos, GATEWAY_ADDRESS);
  }

  uint8_t r = enviarTexto(mesh, (uint8_t)dest, msg, energia);  // una trama o varias si es largo
  bool ok = r == RH_ROUTER_ERROR_NONE;
  if (ok) guardarMensaje(NODE_ADDRESS, dest, msg, true);
  out["ok"] = ok;
  out["seq"] = seq;
  if (!ok) out["error"] = r == RH_ROUTER_ERROR_NO_ROUTE ? "Sin ruta al puesto de mando" : "No se recibió confirmación";
  responderJson(ok ? 200 : 502, out);
}

// POST /api/posicion  {"lat":5.06,"lon":-75.50}
static void apiPosicion() {
  JsonDocument in, out;
  if (deserializeJson(in, server.arg("plain")) || in["lat"].isNull() || in["lon"].isNull()) {
    out["ok"] = false;
    return responderJson(400, out);
  }
  char pos[32];
  snprintf(pos, sizeof(pos), "%.5f,%.5f", in["lat"].as<double>(), in["lon"].as<double>());
  out["ok"] = enviarTrama("POS", pos) == RH_ROUTER_ERROR_NONE;
  responderJson(200, out);
}

static void opciones() {
  cabecerasCors();
  server.send(204);
}

// Cualquier otra URL (detección de portal de Android/iOS/Windows) lleva al portal.
static void redirigirAlPortal() {
  server.sendHeader("Location", String("http://") + WiFi.softAPIP().toString() + "/", true);
  server.send(302, "text/plain", "");
}

static void iniciarWifi() {
  String ssid = String("Emergencia ") + NODE_NAME;
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ssid.c_str());  // red abierta: debe poder usarla cualquiera en una emergencia
  dns.start(53, "*", WiFi.softAPIP());

  server.on("/", HTTP_GET, [] { server.send_P(200, "text/html; charset=utf-8", PORTAL_HTML); });
  server.on("/api/estado", HTTP_GET, apiEstado);
  server.on("/api/mensajes", HTTP_GET, apiMensajes);
  server.on("/api/mensaje", HTTP_POST, apiEnviar);
  server.on("/api/posicion", HTTP_POST, apiPosicion);
  server.on("/api/mensaje", HTTP_OPTIONS, opciones);
  server.on("/api/posicion", HTTP_OPTIONS, opciones);
  server.onNotFound(redirigirAlPortal);
  server.begin();
  Serial.printf("[nodo %d] Wi-Fi \"%s\" en %s\n", NODE_ADDRESS, ssid.c_str(), WiFi.softAPIP().toString().c_str());
}

void setup() {
  Serial.begin(115200);
  delay(300);
  analogReadResolution(12);
  energia = medirEnergia();
  if (!iniciarRadio(mesh, radio)) {
    Serial.println("[nodo] ERROR: no se encontró el RFM69HCW, revisar conexiones SPI");
  }
  mesh.setTimeout(200);
  mesh.setRetries(3);
  iniciarWifi();
  guardarMensaje(NODE_ADDRESS, NODE_ADDRESS, "Nodo encendido", true);
}

void loop() {
  dns.processNextRequest();
  server.handleClient();

  // Radio: recibir mensajes para este nodo y enrutar los de otros (lo hace RHMesh aquí).
  uint8_t len = sizeof(buf) - 1;
  uint8_t from;
  if (mesh.recvfromAckTimeout(buf, &len, 10, &from)) {
    buf[len] = 0;
    Trama t;
    if (leerTrama((const char*)buf, t) && t.msg[0]) {
      if (strcmp(t.tipo, "MSG") == 0) {
        guardarMensaje(from, NODE_ADDRESS, t.msg, false);
      } else if (strcmp(t.tipo, "MSGP") == 0 &&
                 reensamblador.agregar(from, t.msg, textoLargo, sizeof(textoLargo))) {
        guardarMensaje(from, NODE_ADDRESS, textoLargo, false);
      }
    }
  }

  unsigned long ahora = millis();
  if (ahora - ultimaMedicion > 10000) {
    ultimaMedicion = ahora;
    energia = medirEnergia();
  }
  if (ultimoInfo == 0 || ahora - ultimoInfo > INTERVALO_INFO_MS) {
    ultimoInfo = ahora;
    enviarTrama("INFO", NODE_NAME);
  }
  if (ultimoTel == 0 || ahora - ultimoTel > INTERVALO_TEL_MS) {
    ultimoTel = ahora;
    enviarTrama("TEL", "");
  }
}
