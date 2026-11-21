# Configuración de referencia de la red FSK 915 MHz

Los valores reales están en el firmware: [`firmware/include/config.h`](../firmware/include/config.h).
Deben ser **idénticos** en el gateway y en todos los nodos.

## Parámetros de radio (RFM69HCW + RadioHead RHMesh)

| Parámetro | Valor | Dónde se cambia |
|---|---|---|
| Frecuencia | 915,0 MHz (banda ISM libre en Colombia) | `RF_FREQ_MHZ` |
| Modulación | FSK `FSK_Rb9_6Fd19_2` (9,6 kbps, desviación 19,2 kHz) | `iniciarRadio()` en `red.h` |
| Potencia | +20 dBm (RFM69HCW de alta potencia) | `RF_TX_POWER_DBM` |
| Sync words | `0x2D, 0xD4` | `RF_SYNC_WORDS` |
| Cifrado | AES-128 por hardware, clave de 16 bytes | `include/clave.h` (no se sube a git) |
| Malla | RadioHead RHMesh, direcciones 1-254 (1 = gateway) | `NODE_ADDRESS` en `platformio.ini` |
| Texto por mensaje | 36 bytes en una trama (paquete de 54 − 18 de cabecera); hasta 120 partiéndolo en tramas MSGP | `MAX_TEXTO`, `MAX_TEXTO_LARGO` |

## Trama por aire

```
TIPO|BAT_V|PANEL_V|CARGA_PCT|MENSAJE
MSG|12.4|18.1|82|Albergue Coliseo: 280 personas
TEL|12.4|18.1|82|
POS|12.4|18.1|82|5.06012,-75.50111
INFO|12.4|18.1|82|Albergue Coliseo
MSGP|12.4|18.1|82|a3.1.2:primera parte de un mens     (mensaje largo: id a3, parte 1 de 2)
MSGP|12.4|18.1|82|a3.2.2:aje largo
```

## Gateway → servidor (USB, 115.200 baudios, una línea JSON por trama)

```json
{"nodo":2,"tipo":"MSG","bat":12.4,"panel":18.1,"carga":82,"msg":"Albergue Coliseo: 280 personas","rssi":-72}
```

Servidor → gateway: `{"dest":2,"msg":"Brigada en camino"}` (`dest` 255 = todos los nodos conocidos).

## Conexiones (SPI por defecto de cada placa)

| Señal RFM69HCW | ESP32 DevKit V1 | ESP32-S3 DevKitC | ESP32-C6 DevKitC |
|---|---|---|---|
| SCK | 18 | 12 | 6 |
| MISO | 19 | 13 | 2 |
| MOSI | 23 | 11 | 7 |
| NSS (CS) | 5 | 10 | 18 |
| DIO0 (IRQ) | 26 | 9 | 19 |
| RESET | 27 | 14 | 20 |
| 3.3V / GND | 3V3 / GND | 3V3 / GND | 3V3 / GND |

Medición de energía (ADC): batería en GPIO 34 / 4 / 0 con divisor 100 kΩ/22 kΩ; panel en
GPIO 35 / 5 / 1 con divisor 100 kΩ/10 kΩ (ESP32 / S3 / C6). Antena: 1/4 de onda a 915 MHz ≈ **7,8 cm**
de cable en el pin ANT del RFM69HCW.
