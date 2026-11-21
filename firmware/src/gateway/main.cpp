// Gateway del puesto de mando: ESP32-S3 + RFM69HCW, dirección RHMesh 1.
//
// Radio -> PC : por cada trama recibida escribe una línea JSON por USB (115.200 baudios):
//   {"nodo":2,"tipo":"MSG","bat":12.4,"panel":18.1,"carga":82,"msg":"...","rssi":-72}
// PC -> Radio : lee líneas JSON {"dest":2,"msg":"Brigada en camino"} (dest 255 = todos)
//               y las transmite como trama MSG.
// Además reporta su nombre y su energía (el kit del puesto de mando) en líneas marcadas con
// "gw":1, que el servidor guarda en la tabla gateways. Puede haber varios gateways en el
// mismo servidor (cada uno por su USB); el servidor los distingue por el puerto.
#include <ArduinoJson.h>

#include "red.h"

RH_RF69 radio(PIN_RF_CS, PIN_RF_INT);
RHMesh mesh(radio, GATEWAY_ADDRESS);

static uint8_t buf[MAX_PAQUETE + 8];
static Reensamblador reensamblador;
static char textoLargo[MAX_TEXTO_LARGO + 1];
static bool conocido[256] = {false};  // nodos de los que hemos recibido algo
static String lineaPc;
static unsigned long ultimoTel = 0;

static void emitirJsonTexto(uint8_t from, const Trama& t, const char* texto, int rssi) {
  JsonDocument doc;
  doc["nodo"] = from;
  doc["tipo"] = "MSG";
  doc["bat"] = t.bat;
  doc["panel"] = t.panel;
  doc["carga"] = t.carga;
  doc["msg"] = texto;
  doc["rssi"] = rssi;
  serializeJson(doc, Serial);
  Serial.println();
}

static void emitirJson(uint8_t from, const Trama& t, int rssi) {
  JsonDocument doc;
  doc["nodo"] = from;
  doc["tipo"] = t.tipo;
  doc["bat"] = t.bat;
  doc["panel"] = t.panel;
  doc["carga"] = t.carga;
  if (strcmp(t.tipo, "POS") == 0) {
    const char* coma = strchr(t.msg, ',');
    if (coma) {
      doc["lat"] = atof(t.msg);
      doc["lon"] = atof(coma + 1);
    }
  } else if (strcmp(t.tipo, "INFO") == 0) {
    doc["nombre"] = t.msg;
  } else if (t.msg[0]) {
    doc["msg"] = t.msg;
  }
  doc["rssi"] = rssi;
  serializeJson(doc, Serial);
  Serial.println();
}

static void reportarEnergiaPropia() {
  Energia e = medirEnergia();
  JsonDocument doc;
  doc["gw"] = 1;  // línea propia del gateway (no es un nodo)
  doc["nodo"] = GATEWAY_ADDRESS;
  doc["tipo"] = "TEL";
  doc["bat"] = e.bat;
  doc["panel"] = e.panel;
  doc["carga"] = e.carga;
  serializeJson(doc, Serial);
  Serial.println();
}

static bool enviarA(uint8_t dest, const char* texto) {
  return enviarTexto(mesh, dest, texto, medirEnergia()) == RH_ROUTER_ERROR_NONE;
}

static void procesarLineaPc(const String& linea) {
  JsonDocument doc;
  if (deserializeJson(doc, linea)) return;  // no es JSON: se ignora
  int dest = doc["dest"] | (int)BROADCAST_ADDRESS;
  const char* msg = doc["msg"] | "";
  if (!msg[0]) return;

  int enviados = 0, fallidos = 0;
  if (dest == BROADCAST_ADDRESS) {
    // RHMesh no reenvía difusiones: se envía a cada nodo conocido para que llegue por varios saltos.
    for (int a = 2; a < 255; a++) {
      if (!conocido[a]) continue;
      enviarA(a, msg) ? enviados++ : fallidos++;
    }
  } else if (dest >= 2 && dest <= 254) {
    enviarA(dest, msg) ? enviados++ : fallidos++;
  }
  // Línea de estado (sin "nodo": el servidor la registra pero no la trata como trama).
  Serial.printf("{\"tipo\":\"ENVIO\",\"dest\":%d,\"ok\":%d,\"fallidos\":%d}\n", dest, enviados, fallidos);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  analogReadResolution(12);
  if (!iniciarRadio(mesh, radio)) {
    Serial.println("[gateway] ERROR: no se encontró el RFM69HCW, revisar conexiones SPI");
    while (true) delay(1000);
  }
  mesh.setTimeout(200);
  mesh.setRetries(3);
  Serial.printf("{\"gw\":1,\"nodo\":%d,\"tipo\":\"INFO\",\"nombre\":\"%s\"}\n", GATEWAY_ADDRESS, NODE_NAME);
}

void loop() {
  // 1. Radio: recibir (y enrutar tramas de otros nodos, lo hace RHMesh dentro de esta llamada).
  uint8_t len = sizeof(buf) - 1;
  uint8_t from;
  if (mesh.recvfromAckTimeout(buf, &len, 20, &from)) {
    buf[len] = 0;
    conocido[from] = true;
    Trama t;
    bool ok = leerTrama((const char*)buf, t);
    if (ok && strcmp(t.tipo, "MSGP") == 0) {
      // Parte de un mensaje largo: se emite como un solo MSG cuando llegan todas.
      if (reensamblador.agregar(from, t.msg, textoLargo, sizeof(textoLargo))) {
        strcpy(t.tipo, "MSG");
        strncpy(t.msg, "", sizeof(t.msg));
        emitirJsonTexto(from, t, textoLargo, radio.lastRssi());
      }
    } else if (ok) {
      emitirJson(from, t, radio.lastRssi());
    } else {
      Serial.printf("[gateway] trama no reconocida de %d: %s\n", from, (const char*)buf);
    }
  }

  // 2. USB: mensajes del puesto de mando para transmitir.
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      procesarLineaPc(lineaPc);
      lineaPc = "";
    } else if (c != '\r' && lineaPc.length() < 512) {
      lineaPc += c;
    }
  }

  // 3. Energía del kit del puesto de mando.
  if (millis() - ultimoTel > INTERVALO_TEL_MS || ultimoTel == 0) {
    ultimoTel = millis();
    reportarEnergiaPropia();
  }
}
