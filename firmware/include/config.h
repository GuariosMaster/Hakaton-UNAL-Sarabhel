// Parámetros comunes de la red FSK 915 MHz. Deben ser IGUALES en el gateway y en todos los nodos.
#pragma once
#include <Arduino.h>

#ifndef NODE_ADDRESS
#define NODE_ADDRESS 2
#endif
#ifndef NODE_NAME
#define NODE_NAME "Nodo"
#endif

// --- Radio RFM69HCW ----------------------------------------------------------
#define RF_FREQ_MHZ 915.0        // banda ISM libre en Colombia
#define RF_TX_POWER_DBM 20       // máximo del RFM69HCW (módulo de alta potencia)
static const uint8_t RF_SYNC_WORDS[] = {0x2D, 0xD4};

// Clave AES-128 (16 bytes). La real va en include/clave.h, que NO se sube al repositorio:
// copiar clave.example.h como clave.h y cambiar los bytes.
#if __has_include("clave.h")
#include "clave.h"
#else
#warning "Usando la clave AES de ejemplo: crea include/clave.h antes de desplegar"
#include "clave.example.h"
#endif

// --- Red RHMesh --------------------------------------------------------------
#define GATEWAY_ADDRESS 1        // el gateway del puesto de mando
#define BROADCAST_ADDRESS 255    // "todos": el gateway lo envía a cada nodo conocido

// Tamaño de un paquete de datos por radio: el RFM69 transmite 60 bytes (64 cifrables - 4 de
// cabecera) y RHMesh usa 6 (RHRouter 5 + RHMesh 1). OJO: RH_MESH_MAX_MESSAGE_LEN de RadioHead
// vale 249 porque se calcula con el máximo genérico de 255; no sirve para el RFM69.
#define MAX_PAQUETE 54
// Mensaje en una sola trama: "MSG|12.4|18.1|100|" ocupa 18 bytes -> 36 de texto.
#define MAX_TEXTO 36
// Mensajes más largos se parten en tramas MSGP de hasta 28 bytes de texto
// ("MSGP|12.4|18.1|100|" 19 + "a3.1.5:" 7 + 28 = 54), máximo 5 partes.
#define BYTES_FRAGMENTO 28
#define MAX_FRAGMENTOS 5
#define MAX_TEXTO_LARGO 120

// --- Pines (SPI por defecto de cada placa) -------------------------------------
#if defined(CONFIG_IDF_TARGET_ESP32S3)
// ESP32-S3 DevKitC: FSPI SCK 12, MISO 13, MOSI 11
#define PIN_RF_CS 10
#define PIN_RF_INT 9            // DIO0 del RFM69HCW
#define PIN_RF_RST 14
#define PIN_ADC_BAT 4
#define PIN_ADC_PANEL 5
#elif defined(CONFIG_IDF_TARGET_ESP32C6)
// ESP32-C6 DevKitC: SPI SCK 6, MISO 2, MOSI 7
#define PIN_RF_CS 18
#define PIN_RF_INT 19
#define PIN_RF_RST 20
#define PIN_ADC_BAT 0
#define PIN_ADC_PANEL 1
#else
// ESP32 DevKit V1: VSPI SCK 18, MISO 19, MOSI 23
#define PIN_RF_CS 5
#define PIN_RF_INT 26
#define PIN_RF_RST 27
#define PIN_ADC_BAT 34
#define PIN_ADC_PANEL 35
#endif

// --- Medición de energía (divisores resistivos hacia el ADC, máx. ~3,1 V) --------
// Batería LiFePO4 4S (12,8 V nominal, 14,6 V máx.): divisor 100 kΩ / 22 kΩ -> factor 5,545
#define FACTOR_DIVISOR_BAT 5.545f
// Panel solar 12 V (Voc ~22 V): divisor 100 kΩ / 10 kΩ -> factor 11
#define FACTOR_DIVISOR_PANEL 11.0f

// Intervalos de reporte al puesto de mando
#define INTERVALO_TEL_MS (5UL * 60UL * 1000UL)    // telemetría de energía cada 5 min
#define INTERVALO_INFO_MS (30UL * 60UL * 1000UL)  // nombre del nodo cada 30 min
