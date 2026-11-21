// Funciones comunes: radio RFM69HCW + RHMesh, trama por aire y medición de energía.
#pragma once
#include <Arduino.h>
#include <RHMesh.h>
#include <RH_RF69.h>
#include <SPI.h>

#include "config.h"

// ---------------------------------------------------------------------------
// Trama por aire: TIPO|BAT_V|PANEL_V|CARGA_PCT|MENSAJE
//   MSG|12.4|18.1|82|Albergue Coliseo: 280 personas
//   MSGP|12.4|18.1|82|a3.1.2:primera parte de un mensaje   (mensaje largo, parte 1 de 2)
//   TEL|12.4|18.1|82|
//   POS|12.4|18.1|82|5.06012,-75.50111
//   INFO|12.4|18.1|82|Albergue Coliseo
// ---------------------------------------------------------------------------
struct Trama {
  char tipo[5];
  float bat;
  float panel;
  int carga;
  char msg[MAX_PAQUETE + 1];
};

inline size_t armarTrama(char* out, size_t cap, const char* tipo, float bat, float panel, int carga,
                         const char* msg) {
  int n = snprintf(out, cap, "%s|%.1f|%.1f|%d|%s", tipo, bat, panel, carga, msg ? msg : "");
  if (n < 0) return 0;
  return (size_t)n < cap ? (size_t)n : cap - 1;  // recortado si no cabe
}

inline bool leerTrama(const char* s, Trama& t) {
  const char* p[4];
  const char* c = s;
  for (int i = 0; i < 4; i++) {
    c = strchr(c, '|');
    if (!c) return false;
    p[i] = ++c;
  }
  size_t lt = p[0] - s - 1;
  if (lt == 0 || lt >= sizeof(t.tipo)) return false;
  memcpy(t.tipo, s, lt);
  t.tipo[lt] = 0;
  t.bat = atof(p[0]);
  t.panel = atof(p[1]);
  t.carga = atoi(p[2]);
  strncpy(t.msg, p[3], sizeof(t.msg) - 1);
  t.msg[sizeof(t.msg) - 1] = 0;
  return true;
}

// ---------------------------------------------------------------------------
// Energía: voltaje de batería y panel por ADC, y % de carga LiFePO4 4S en reposo.
// ---------------------------------------------------------------------------
inline float leerVoltaje(int pin, float factor) {
  uint32_t mv = 0;
  for (int i = 0; i < 16; i++) mv += analogReadMilliVolts(pin);
  return (mv / 16.0f) * factor / 1000.0f;
}

inline int cargaLiFePO4(float v) {
  static const float tabla[][2] = {{13.60f, 100}, {13.40f, 90}, {13.30f, 70}, {13.20f, 40},
                                   {13.10f, 30},  {13.00f, 20}, {12.90f, 14}, {12.80f, 9},
                                   {12.50f, 5},   {12.00f, 0}};
  const int n = sizeof(tabla) / sizeof(tabla[0]);
  if (v >= tabla[0][0]) return 100;
  if (v <= tabla[n - 1][0]) return 0;
  for (int i = 1; i < n; i++) {
    if (v >= tabla[i][0]) {
      float f = (v - tabla[i][0]) / (tabla[i - 1][0] - tabla[i][0]);
      return (int)(tabla[i][1] + f * (tabla[i - 1][1] - tabla[i][1]) + 0.5f);
    }
  }
  return 0;
}

struct Energia {
  float bat;
  float panel;
  int carga;
};

inline Energia medirEnergia() {
  Energia e;
  e.bat = leerVoltaje(PIN_ADC_BAT, FACTOR_DIVISOR_BAT);
  e.panel = leerVoltaje(PIN_ADC_PANEL, FACTOR_DIVISOR_PANEL);
  e.carga = cargaLiFePO4(e.bat);
  return e;
}

// ---------------------------------------------------------------------------
// Radio
// ---------------------------------------------------------------------------
// mesh.init() inicializa el driver con valores por defecto (434 MHz, sin cifrado),
// por eso los parámetros de la red se aplican DESPUÉS de mesh.init().
inline bool iniciarRadio(RHMesh& mesh, RH_RF69& radio) {
  pinMode(PIN_RF_RST, OUTPUT);  // reinicio del RFM69HCW (activo en alto)
  digitalWrite(PIN_RF_RST, HIGH);
  delay(10);
  digitalWrite(PIN_RF_RST, LOW);
  delay(10);
  if (!mesh.init()) return false;
  radio.setFrequency(RF_FREQ_MHZ);
  radio.setModemConfig(RH_RF69::FSK_Rb9_6Fd19_2);   // 9,6 kbps, desviación 19,2 kHz
  radio.setTxPower(RF_TX_POWER_DBM, true);           // true = RFM69HCW (alta potencia)
  radio.setSyncWords(RF_SYNC_WORDS, sizeof(RF_SYNC_WORDS));
  radio.setEncryptionKey((uint8_t*)RF_AES_KEY);      // AES-128 por hardware
  return true;
}

// ---------------------------------------------------------------------------
// Mensajes largos: se parten en tramas MSGP "id.k.n:texto" y se reensamblan al llegar.
// ---------------------------------------------------------------------------
// Corta s en trozos de hasta BYTES_FRAGMENTO bytes sin partir caracteres UTF-8 (tildes, ñ).
inline int fragmentar(const char* s, char trozos[][BYTES_FRAGMENTO + 1]) {
  int n = 0;
  size_t len = strlen(s), i = 0;
  while (i < len && n < MAX_FRAGMENTOS) {
    size_t fin = i + BYTES_FRAGMENTO;
    if (fin >= len) {
      fin = len;
    } else {
      while (fin > i && ((uint8_t)s[fin] & 0xC0) == 0x80) fin--;  // no cortar un carácter UTF-8
    }
    memcpy(trozos[n], s + i, fin - i);
    trozos[n][fin - i] = 0;
    n++;
    i = fin;
  }
  return n;
}

// Envía un texto: una trama MSG si cabe, o varias MSGP. Devuelve RH_ROUTER_ERROR_NONE si
// todas las partes fueron confirmadas por la malla.
inline uint8_t enviarTexto(RHMesh& mesh, uint8_t dest, const char* texto, const Energia& e) {
  char trama[MAX_PAQUETE + 1];
  if (strlen(texto) <= MAX_TEXTO) {
    size_t n = armarTrama(trama, sizeof(trama), "MSG", e.bat, e.panel, e.carga, texto);
    return mesh.sendtoWait((uint8_t*)trama, n, dest);
  }
  char trozos[MAX_FRAGMENTOS][BYTES_FRAGMENTO + 1];
  int partes = fragmentar(texto, trozos);
  uint8_t id = (uint8_t)(esp_random() & 0xFF);
  for (int k = 0; k < partes; k++) {
    char cuerpo[BYTES_FRAGMENTO + 12];
    snprintf(cuerpo, sizeof(cuerpo), "%02x.%d.%d:%s", id, k + 1, partes, trozos[k]);
    size_t n = armarTrama(trama, sizeof(trama), "MSGP", e.bat, e.panel, e.carga, cuerpo);
    uint8_t r = mesh.sendtoWait((uint8_t*)trama, n, dest);
    if (r != RH_ROUTER_ERROR_NONE) return r;
  }
  return RH_ROUTER_ERROR_NONE;
}

// Reensambla tramas MSGP de varios remitentes a la vez.
class Reensamblador {
 public:
  // Devuelve true y deja el texto completo en `out` cuando llega la última parte.
  bool agregar(uint8_t de, const char* msg, char* out, size_t cap) {
    unsigned id, k, n;
    int usados = 0;
    if (sscanf(msg, "%x.%u.%u:%n", &id, &k, &n, &usados) != 3 || usados == 0) return false;
    if (n == 0 || n > MAX_FRAGMENTOS || k == 0 || k > n) return false;
    Ranura& r = ranura(de, (uint8_t)id);
    if (r.total != n) {
      r.total = n;
      r.recibidas = 0;
    }
    r.t = millis();
    strncpy(r.partes[k - 1], msg + usados, BYTES_FRAGMENTO);
    r.partes[k - 1][BYTES_FRAGMENTO] = 0;
    r.recibidas |= (1u << (k - 1));
    if (r.recibidas != (1u << r.total) - 1) return false;
    out[0] = 0;
    for (unsigned i = 0; i < r.total; i++) strncat(out, r.partes[i], cap - strlen(out) - 1);
    r.de = 0;  // libera la ranura
    return true;
  }

 private:
  struct Ranura {
    uint8_t de = 0, id = 0;
    unsigned total = 0, recibidas = 0;
    unsigned long t = 0;
    char partes[MAX_FRAGMENTOS][BYTES_FRAGMENTO + 1];
  };
  Ranura ranuras[6];

  Ranura& ranura(uint8_t de, uint8_t id) {
    Ranura* libre = &ranuras[0];
    for (auto& r : ranuras) {
      if (r.de == de && r.id == id && millis() - r.t < 60000) return r;
      if (r.de == 0 || millis() - r.t > 60000 || r.t < libre->t) libre = &r;
    }
    libre->de = de;
    libre->id = id;
    libre->total = 0;
    libre->recibidas = 0;
    return *libre;
  }
};
