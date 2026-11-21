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
//   TEL|12.4|18.1|82|
//   POS|12.4|18.1|82|5.06012,-75.50111
//   INFO|12.4|18.1|82|Albergue Coliseo
// ---------------------------------------------------------------------------
struct Trama {
  char tipo[5];
  float bat;
  float panel;
  int carga;
  char msg[RH_MESH_MAX_MESSAGE_LEN];
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
