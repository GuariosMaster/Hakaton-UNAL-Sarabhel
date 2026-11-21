# Guía de configuración del gateway (ESP32-S3 + RFM69HCW)

Documento para quien arme y configure el gateway del puesto de mando. Explica **qué hace**, **qué
datos pasan por él**, **qué parámetros deben coincidir con el resto del sistema** y **cómo verificar**
que quedó bien. El firmware ya está escrito en [`src/gateway/main.cpp`](src/gateway/main.cpp); los
valores de esta guía salen de ahí y de [`include/config.h`](include/config.h).

---

## 1. Qué es el gateway y qué hace

```
 Nodos de albergue (ESP32 + RFM69HCW) ~~~ radio FSK 915 MHz, malla RHMesh ~~~► GATEWAY ──USB──► Portátil (servidor)
                                                                               dirección 1
```

El gateway es un **nodo más de la malla** (dirección **1**) con dos funciones:

1. **Puente radio ↔ PC.** Todo lo que recibe por radio lo convierte en **una línea de texto JSON** y la
   envía por el **USB** al portátil del puesto de mando. Y lo que el portátil le escribe por USB
   (mensajes del puesto de mando) lo transmite por radio.
2. **Enrutador de la malla.** Como cualquier nodo RHMesh, reenvía paquetes de otros nodos que pasen por
   él (eso lo hace la librería automáticamente; no hay que configurarlo).

Además mide y reporta la **energía del kit del puesto de mando** (batería y panel) como si fuera el nodo 1.

**No usa Wi‑Fi** ni Bluetooth. Solo radio RFM69HCW + USB.

---

## 2. Materiales

| Elemento | Detalle |
|---|---|
| Placa | **ESP32-S3 DevKitC-1** (con USB nativo; el puerto marcado “USB”, no “UART”) |
| Radio | **RFM69HCW 915 MHz** (la versión **H** = alta potencia, +20 dBm) |
| Antena | Cable de **7,8 cm** (1/4 de onda a 915 MHz) soldado al pin ANT, recto y vertical; o antena SMA/u.FL de 915 MHz |
| Condensador | 100 µF entre 3V3 y GND cerca del RFM69HCW (al transmitir pide picos de ~130 mA) |
| Cable USB | De datos (no solo de carga), del ESP32-S3 al portátil |
| Opcional | Divisores resistivos para medir batería (100 kΩ/22 kΩ) y panel (100 kΩ/10 kΩ) del kit del puesto de mando |

> ⚠️ El RFM69HCW funciona **solo a 3,3 V**. Conectarlo a 5 V lo daña.

---

## 3. Conexiones

| RFM69HCW | ESP32-S3 | Para qué |
|---|---|---|
| VIN / 3.3V | **3V3** | Alimentación |
| GND | **GND** | Tierra |
| SCK | **GPIO 12** | Reloj SPI |
| MISO | **GPIO 13** | Datos radio → ESP32 |
| MOSI | **GPIO 11** | Datos ESP32 → radio |
| NSS / CS | **GPIO 10** | Selección del chip |
| DIO0 / G0 | **GPIO 9** | Aviso de “paquete recibido / enviado” |
| RESET | **GPIO 14** | Reinicio de la radio al encender |
| ANT | antena 7,8 cm | — |

Medición de energía (opcional): batería → divisor → **GPIO 4**; panel → divisor → **GPIO 5**.
Si no se conectan, el gateway funciona igual (reporta 0 V).

Si se usan otros pines, cambiarlos en `include/config.h` (bloque `CONFIG_IDF_TARGET_ESP32S3`).

---

## 4. Parámetros de radio (deben ser IGUALES en el gateway y en TODOS los nodos)

Si uno solo de estos valores difiere, **los nodos no se escuchan** (no da error, simplemente no llega nada).

| Parámetro | Valor | Dónde está |
|---|---|---|
| Frecuencia | **915,0 MHz** | `RF_FREQ_MHZ` en `config.h` |
| Modulación | **FSK, 9,6 kbps, desviación 19,2 kHz** (`FSK_Rb9_6Fd19_2`) | `iniciarRadio()` en `red.h` |
| Potencia | **+20 dBm**, modo alta potencia (`setTxPower(20, true)`) | `RF_TX_POWER_DBM` |
| Sync words | **0x2D, 0xD4** | `RF_SYNC_WORDS` |
| Cifrado | **AES-128**, clave de **16 bytes** | `include/clave.h` (ver abajo) |
| Protocolo de malla | **RadioHead RHMesh** | librería `mikem/RadioHead` |
| Dirección del gateway | **1** (fija; los nodos le envían a la 1) | `-DNODE_ADDRESS=1` en `platformio.ini` |
| Direcciones de nodos | **2 a 254**, una distinta por nodo | `platformio.ini` de cada nodo |
| Reintentos / espera | 3 reintentos, 200 ms | `mesh.setRetries(3)`, `mesh.setTimeout(200)` |

### La clave AES

1. Copiar `include/clave.example.h` como **`include/clave.h`**.
2. Cambiar los 16 bytes por valores propios (cualquier combinación).
3. **Copiar ese mismo `clave.h`** a todos los que carguen nodos. **No subirlo a GitHub** (ya está en
   `.gitignore`). Si se compila sin `clave.h`, el firmware avisa y usa la clave de ejemplo, que es pública.

---

## 5. Qué datos viajan

Hay **tres tramos** y cada uno tiene su formato.

### 5.1 Por radio (nodo ↔ gateway): trama de texto

```
TIPO|BAT_V|PANEL_V|CARGA_PCT|MENSAJE
```

| TIPO | Lo envía | Cuándo | MENSAJE | Ejemplo |
|---|---|---|---|---|
| `MSG` | nodo o gateway | Cada reporte o SOS (desde el portal o la app) | Texto de hasta 36 bytes | `MSG|12.4|18.1|82|Albergue Coliseo: 280 personas` |
| `MSGP` | nodo o gateway | Mensajes de 37 a 120 bytes, partidos en hasta 5 partes | `id.parte.total:texto` | `MSGP|12.4|18.1|82|a3.1.2:SOS 3 personas atrapadas` |
| `TEL` | nodo | Cada **5 min** (telemetría de energía) | vacío | `TEL|12.4|18.1|82|` |
| `POS` | nodo | Antes de un SOS enviado con GPS del teléfono | `lat,lon` (5 decimales) | `POS|12.4|18.1|82|5.06012,-75.50111` |
| `INFO` | nodo | Al encender y cada **30 min** | Nombre del albergue | `INFO|12.4|18.1|82|Albergue Coliseo` |

- `BAT_V` = voltaje de la batería (V, 1 decimal) · `PANEL_V` = voltaje del panel solar (V) ·
  `CARGA_PCT` = carga estimada de la batería (0–100 %). **Toda trama lleva la energía del nodo.**
- **Tamaño máximo: 54 bytes por paquete** (el RFM69 transmite 60 y RHMesh usa 6 de cabecera). Por eso
  el texto cabe en 36 bytes; más largo se parte en `MSGP` y el gateway lo **reensambla** antes de
  mandarlo al PC.
- La trama va **cifrada** (AES-128) y RHMesh pide **confirmación (ACK)** salto a salto.

### 5.2 Por USB (gateway → portátil): una línea JSON por trama

Velocidad **115.200 baudios**, una línea terminada en `\n` por cada trama recibida:

```json
{"nodo":2,"tipo":"MSG","bat":12.4,"panel":18.1,"carga":82,"msg":"Albergue Coliseo: 280 personas","rssi":-72}
{"nodo":2,"tipo":"TEL","bat":12.4,"panel":18.1,"carga":82,"rssi":-70}
{"nodo":2,"tipo":"POS","bat":12.4,"panel":18.1,"carga":82,"lat":5.06012,"lon":-75.50111,"rssi":-71}
{"nodo":2,"tipo":"INFO","bat":12.4,"panel":18.1,"carga":82,"nombre":"Albergue Coliseo","rssi":-70}
```

| Campo | Tipo | Significado |
|---|---|---|
| `nodo` | entero 1–254 | Dirección RHMesh de quien envió (el servidor lo muestra como `nodo-2`) |
| `tipo` | texto | `MSG`, `TEL`, `POS`, `INFO` (los `MSGP` llegan ya unidos como `MSG`) |
| `bat`, `panel` | número | Voltajes en V |
| `carga` | entero | % de batería |
| `msg` | texto | Solo en `MSG` |
| `lat`, `lon` | número | Solo en `POS` |
| `nombre` | texto | Solo en `INFO` |
| `rssi` | entero (dBm) | Intensidad con que llegó la señal: −60 excelente, −90 aceptable, −100 al límite |

El gateway también imprime:
- Al encender: `{"gw":1,"nodo":1,"tipo":"INFO","nombre":"Puesto de mando"}` y su propia energía
  (`{"gw":1,"nodo":1,"tipo":"TEL",…}`). El campo **`"gw":1`** indica que la línea es del propio gateway:
  el servidor la guarda en la tabla **gateways** (no como un nodo).
- Tras cada envío: `{"tipo":"ENVIO","dest":2,"ok":1,"fallidos":0}` (cuántos nodos confirmaron).
- Mensajes de diagnóstico que **empiezan con `[`**, por ejemplo `[gateway] ERROR: …`. El servidor ignora
  todo lo que no sea JSON con campo `nodo`, así que no molestan.

### 5.3 Por USB (portátil → gateway): mensajes del puesto de mando

Una línea JSON por mensaje:

```json
{"dest":2,"msg":"Brigada en camino"}
{"dest":255,"msg":"Atención: réplica fuerte, salgan a zonas abiertas"}
```

- `dest`: dirección del nodo (2–254) o **255 = todos los nodos conocidos**. Como RHMesh no reenvía las
  difusiones, el gateway envía el mensaje **a cada nodo del que ya recibió algo**.
- `msg`: hasta **120 bytes** (se parte en `MSGP` si pasa de 36).
- Esto lo hace el servidor automáticamente; solo hace falta escribirlo a mano para probar (sección 7).

### 5.4 Cuánto tráfico es

A 9,6 kbps un paquete completo tarda **≈ 60 ms** en el aire. Con 10 albergues enviando telemetría cada
5 minutos y algunos mensajes, el canal está ocupado **menos del 1 %** del tiempo. Un mensaje largo
(5 partes) tarda ≈ 0,5 s con sus confirmaciones.

---

## 6. Cargar el firmware

Requiere **PlatformIO** (extensión de VS Code, o `pip install platformio`).

```bash
cd firmware
cp include/clave.example.h include/clave.h       # y cambiar los 16 bytes (sección 4)
pio run -e gateway_esp32s3 -t upload              # compila y carga el gateway
pio device monitor -b 115200                      # ver lo que imprime
```

- Conectar el ESP32-S3 por el puerto **USB** (el nativo). Si no aparece o no carga: mantener **BOOT**,
  pulsar **RESET**, soltar BOOT y volver a cargar.
- En Windows aparece como un puerto **COM** (ver en el Administrador de dispositivos → Puertos).
  En Linux como **`/dev/ttyACM0`** (el usuario debe estar en el grupo `dialout`).

### Conectarlo al servidor

```powershell
cd server
.\iniciar.ps1 -Radio usb                # detecta el puerto del ESP32-S3 solo
.\iniciar.ps1 -Radio usb -Puerto COM5   # o indicarlo
```

En Linux con Docker: `MESH_USB_DEVICE=/dev/ttyACM0 docker compose -f docker-compose.yml -f docker-compose.serial.yml up -d`.

> Cierra el monitor de PlatformIO antes de iniciar el servidor: **solo un programa puede usar el
> puerto USB a la vez.**

---

## 7. Lista de verificación

| # | Prueba | Qué se debe ver |
|---|---|---|
| 1 | Encender con el monitor abierto | `{"nodo":1,"tipo":"INFO","nombre":"Puesto de mando"}` y una línea `TEL`. Si sale `[gateway] ERROR: no se encontró el RFM69HCW`, revisar cableado SPI y 3,3 V. |
| 2 | Escribir en el monitor `{"dest":255,"msg":"prueba"}` + Enter | `{"tipo":"ENVIO","dest":255,"ok":0,"fallidos":0}` (0 porque aún no conoce nodos: es normal). |
| 3 | Encender un nodo de albergue (con la **misma clave**) | En segundos llega su `INFO` y su `TEL` con `"nodo":2` y un `rssi`. |
| 4 | Enviar un reporte desde el portal del nodo | Línea `MSG` con el texto. |
| 5 | Repetir la prueba 2 | Ahora `"ok":1`, y el mensaje aparece en el portal del nodo. |
| 6 | Cerrar el monitor e iniciar `iniciar.ps1 -Radio usb` | El nodo aparece en el dashboard (`http://localhost:8080`) con su energía. |
| 7 | Alejar el nodo y anotar el `rssi` | Medir el alcance real; por debajo de −100 dBm empiezan a perderse paquetes. |

---

## 8. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `no se encontró el RFM69HCW` | Cableado SPI, CS o alimentación | Revisar tabla de la sección 3; medir 3,3 V en el módulo |
| No llega nada de los nodos | Clave, frecuencia o sync words distintas | Compilar gateway y nodos con el **mismo** `clave.h` y `config.h` |
| Llega con RSSI muy bajo | Antena mal (longitud, doblada, sin antena) | Antena de 7,8 cm recta y vertical; gateway en un punto alto |
| Se reinicia al transmitir | Caída de tensión por el pico de corriente | Condensador de 100 µF; mejor cable/puerto USB |
| El servidor no encuentra el gateway | Puerto ocupado o no detectado | Cerrar el monitor; indicar el puerto con `-Puerto COMx` |
| `ENVIO ... "fallidos":1` | El nodo está fuera de alcance o apagado | Acercar, poner un nodo repetidor intermedio |

---

## 9. Varios gateways

El servidor puede leer **varios gateways a la vez**, cada uno por su USB:

```powershell
$env:MESH_GATEWAY_NAMES = "Puesto UNAL,Torre Chipre"   # opcional, mismo orden que los puertos
.\iniciar.ps1 -Radio usb -Puerto "COM5,COM7"
```

(En Linux: `MESH_USB_DEVICE=/dev/ttyACM0,/dev/ttyACM1`.) Sin indicar puertos, detecta todos los
ESP32 conectados. Cada gateway queda como `gw-1`, `gw-2`… y el servidor:

- Guarda cada gateway en la tabla **gateways** (estado, energía, última vez que habló) y avisa con una
  alerta **“Gateway desconectado”** si se suelta el cable o deja de responder 2,5 minutos.
- Guarda en la tabla **enlaces** qué gateway escucha a qué nodo y con qué señal (promedio móvil).
- **Descarta los duplicados** cuando dos gateways reciben la misma trama.
- Envía cada mensaje del puesto de mando **por el gateway que mejor escucha** a ese nodo; los mensajes
  para “todos” salen por todos los gateways.
- Muestra en el dashboard el panel **Gateways** y, en el mapa, las líneas gateway ↔ nodo según la señal.

> ⚠️ **Importante si varios gateways comparten la misma malla** (misma frecuencia, sync words y clave):
> hoy todos los gateways usan la dirección **1** y los nodos le envían a la 1. Dos gateways con la
> dirección 1 en la misma malla confunden el enrutamiento de RHMesh. Mientras no se cambie el firmware
> de los nodos (para elegir entre varias direcciones de gateway), hay dos opciones seguras:
> - **Mallas separadas**: cada gateway con su zona y **sync words distintas** (p. ej. `0x2D,0xD4` y
>   `0x2D,0xD5`), todos conectados al mismo servidor. Recomendado.
> - Un solo gateway por malla y los demás de repuesto, apagados.

## 10. Lo que NO se debe cambiar sin avisar al equipo

Estas cosas son el “contrato” entre firmware, servidor y app. Si cambian, hay que cambiar también el
servidor (`server/sarabhel/gateway.py`) y la app:

- La **dirección 1** del gateway.
- El **formato de la trama** `TIPO|BAT_V|PANEL_V|CARGA_PCT|MENSAJE` y los tipos `MSG/MSGP/TEL/POS/INFO`.
- Los **nombres de los campos JSON** (`nodo`, `tipo`, `bat`, `panel`, `carga`, `msg`, `lat`, `lon`, `nombre`, `rssi`, `dest`).
- La velocidad del USB: **115.200 baudios**.
- El campo **`"gw":1`** en las líneas propias del gateway.
- Los límites de **54 bytes por paquete** y **120 bytes por mensaje**.

## 11. Pendiente de ajustar con el hardware real

- **Calibrar los divisores** de batería y panel (comparar con un multímetro y ajustar
  `FACTOR_DIVISOR_BAT` / `FACTOR_DIVISOR_PANEL`).
- **Medir el alcance** entre el gateway y cada albergue, y decidir dónde poner repetidores.
- Verificar la **potencia permitida** en la banda 915–928 MHz con la regulación de la ANE.
- Probar el **reensamblado de mensajes largos** (el código compila pero no se ha probado en radio real).
