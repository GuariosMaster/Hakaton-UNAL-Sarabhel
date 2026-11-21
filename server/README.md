# Servidor local de mensajería de emergencia — Equipo Sarabhel

Servidor del puesto de mando que recibe los mensajes de la red **FSK 915 MHz** (transceptores RFM69HCW, gateway ESP32-S3 por USB nativo), los clasifica por prioridad, rastrea la ubicación GPS de los nodos y los muestra en un mapa web. Funciona **sin internet** y está pensado para correr en un portátil alimentado por batería o panel solar.

## Arquitectura

```
 Nodos FSK 915 MHz (RFM69HCW + ESP32) ──radio──► Gateway ESP32-S3 ──USB CDC──► Listener
                                                                               │
                                                         Mosquitto (MQTT, pub/sub)
                                    ┌───────────────────────┼────────────────────────┬──────────────────────┐
                               Mensajería              Localización              Triaje IA              Dashboard
                       (prioridad, buzón, envío)(GPS, historial, geocercas)  (Ollama Qwen 2.5 1.5B)(API + mapa en vivo)
                                    │                       │                        │                      │
                                    └───────────────────────┴────────► SQLite (WAL) ◄┴──────────────────────┘
```

| Servicio | Archivo | Qué hace |
|---|---|---|
| **Broker** | Mosquitto | Bus publicación/suscripción con persistencia (QoS 1). |
| **Listener** | `sarabhel/listener.py` | Lee el gateway ESP32-S3 por USB serial (pyserial, 115.200 baudios), traduce cada trama JSON a eventos y los publica en Mosquitto. Escribe en el gateway los mensajes de `red/tx/msg` para transmitirlos por radio. |
| **Mensajería** | `sarabhel/messaging.py` | Clasifica (crítico / moderado / informativo), adjunta la última posición del remitente, guarda en SQLite y emite alertas. |
| **Localización** | `sarabhel/location.py` | Guarda posiciones GPS e historial, nombre y energía de cada nodo (batería V, panel V, % carga), detecta entrada a zonas de riesgo y alerta de batería baja. |
| **Triaje IA** | `sarabhel/triage.py` | Motor de triaje inteligente 100% offline: consume `events/msg`, consulta el LLM local (`qwen2.5:1.5b` en Ollama) bajo la taxonomía EDAN, extrae necesidades tácticas, genera resúmenes operativos, persiste en la tabla `triage` y publica `events/triage`. |
| **Dashboard** | `sarabhel/dashboard.py` + `static/` | API REST, eventos en vivo (SSE) con soporte de badges EDAN y mapa Leaflet incluido localmente (no usa CDN). |

### ¿Por qué no Kubernetes?
Un clúster de Kubernetes (aunque sea k3s) consume entre 0,5 y 1 GB de RAM y CPU constante en el plano de control, lo que reduce la autonomía de la batería y agrega piezas que pueden fallar. Con Docker Compose y procesos Python conservamos el mismo diseño de microservicios desacoplados por un broker, pero con unos cientos de MB en total y un solo comando para levantar o reiniciar todo.

### Temas MQTT

| Tema | Publica | Contenido |
|---|---|---|
| `red/albergue/{nodo_id}/msg` | listener | Mensaje de texto recibido por RF FSK |
| `red/albergue/{nodo_id}/tel` | listener | Telemetría energética (batería, panel, carga) |
| `red/albergue/{nodo_id}/pos` | listener | Posición GPS del nodo |
| `red/albergue/{nodo_id}/info` | listener | Nombre del nodo |
| `app/send` | dashboard | Mensaje escrito en el puesto de mando (lo guarda el servicio de mensajería) |
| `red/tx/msg` | mensajería | Mensaje a transmitir por radio: `{text, to}` → el listener lo escribe en el gateway |

`{nodo_id}` es `nodo-N` para los nodos de radio (dirección RHMesh N) o `!xxxxxxxx` para los teléfonos
conectados por Wi‑Fi al puesto de mando (endpoints `/api/device/*`).
| `events/msg` · `events/position` · `events/node` · `events/alert` · `events/triage` | servicios | Datos ya procesados, clasificados y guardados |

### Aceleración GPU para Ollama (opcional)
Si el servidor del puesto de mando cuenta con GPU NVIDIA, se puede activar la aceleración por hardware agregando el archivo override:
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

## Puesta en marcha

### A) Servidor Ubuntu con Docker (despliegue final)

```bash
cp .env.example .env
# Demo sin hardware RF (modo simulado):
docker compose up -d --build
# Gateway ESP32-S3 conectado por USB nativo (aparece como /dev/ttyACM0):
MESH_USB_DEVICE=/dev/ttyACM0 docker compose -f docker-compose.yml -f docker-compose.serial.yml up -d --build
# Variables relevantes: MESH_CONNECTION=usb, MESH_USB_DEVICE, MESH_USB_BAUD=115200
```

Abrir `http://<ip-del-servidor>:8080` desde cualquier equipo de la red local.
Ver los registros: `docker compose logs -f listener mensajeria`.

### B) Windows sin Docker (demo en el portátil)

```powershell
.\iniciar.ps1                     # nodos FSK simulados
.\iniciar.ps1 -Radio usb          # gateway ESP32-S3 por USB (detecta el puerto)
.\iniciar.ps1 -Radio usb -Puerto COM5
.\iniciar.ps1 -Radio ninguno      # solo teléfonos por Wi-Fi
```

Abre una ventana por servicio y muestra la IP que deben usar los teléfonos.

### C) Linux/macOS sin Docker (desarrollo)

Se necesita un broker MQTT: instalar Mosquitto, o para pruebas usar `amqtt` (pure Python).

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt amqtt
# Cada uno en su propia terminal:
.venv/bin/amqtt
.venv/bin/python -m sarabhel.messaging
.venv/bin/python -m sarabhel.location
.venv/bin/python -m sarabhel.dashboard
# Modo simulado (sin hardware):
MESH_CONNECTION=sim .venv/bin/python -m sarabhel.listener
# Con gateway ESP32-S3 por USB:
MESH_CONNECTION=usb MESH_USB_DEVICE=/dev/ttyACM0 .venv/bin/python -m sarabhel.listener
```

Sin `MESH_CONNECTION` el listener arranca en **modo simulado**: nodos ficticios FSK en Manizales que envían posiciones, mensajes (incluidos SOS) y telemetría energética.

### Pruebas

```bash
.venv/bin/python -m pytest -q tests
```

## Configuración de los nodos RFM69HCW

El firmware está en [`firmware/`](../firmware/) y los parámetros en [`firmware/include/config.h`](../firmware/include/config.h). Cada nodo (ESP32 + RFM69HCW) y el gateway (ESP32-S3 + RFM69HCW) deben compartir los mismos parámetros RF:

| Parámetro | Valor | Justificación |
|---|---|---|
| Frecuencia portadora | 915,0 MHz | Banda ISM libre en Colombia |
| Modulación | FSK (`FSK_Rb9_6Fd19_2`) | 9,6 kbps, baja tiempo en el aire (~42 ms por paquete de 50 bytes) |
| Potencia TX | +20 dBm | Máxima del RFM69HCW |
| Protocolo malla | RadioHead RHMesh | Enrutamiento multi-salto, ACK, direccionamiento ID 1-254 |
| Cifrado | AES-128 por hardware | Sin carga extra en el ESP32 |
| Sync Word | 0x2D, 0xD4 | Filtrado de ruido en 915 MHz |
| Trama por aire | `TIPO|BAT_V|PANEL_V|CARGA_PCT|MENSAJE` (TIPO: MSG, TEL, POS, INFO) | Ej: `MSG|12.4|18.1|82|Albergue Coliseo: 280 personas` (texto máx. 36 bytes) |
| USB Serial (gateway → PC) | JSON a 115.200 baudios | Ej: `{"nodo":2,"tipo":"MSG","bat":12.4,"panel":18.1,"carga":82,"msg":"...","rssi":-72}` |

## Límites de comunicación, capacidades y tiempos (según datasheets RFM69HCW y ESP32-S3)

### Arquitectura de capas: ¿Por qué 120 bytes en el servidor y 54 bytes por aire?

No hay inconsistencia entre los 120 bytes que recibe el servidor y los límites de la radio; se trata de **segmentación en capa de transporte**:

- **Capa de aplicación (App / Servidor / Dashboard):** Acepta un mensaje lógico de hasta **120 bytes** UTF-8 (`USB_MAX_TEXT_BYTES`). Es la unidad de lectura y escritura del usuario.
- **Capa física y de enlace (RFM69HCW + RHMesh):** El transceptor tiene una FIFO de 66 bytes. Con cifrado hardware AES-128 (bloques de 16 bytes, máx. 64 bytes de mensaje) y cabeceras de red RHMesh (driver + router + mesh = 10 bytes), la MTU física de radio es de **54 bytes** (`MAX_PAQUETE`).
- **Capa de adaptación (Firmware):** Segmenta automáticamente mensajes mayores a 36 bytes en fragmentos `MSGP` y los reensambla en destino.

### Desglose exacto del payload: ¿Por qué se necesitan hasta 5 tramas y no 3?

Un error de cálculo común es dividir $120 \div 50 \approx 2,4$ y asumir que con 3 tramas basta. Esto olvida que el texto **no viaja solo**: cada trama de radio transporta telemetría del nodo y control de fragmentación.

| Tipo de trama | Tamaño total paquete RF | Overhead de telemetría y cabecera | Texto útil por trama | Tramas necesarias para el texto |
|---|---|---|---|---|
| **Corta (`MSG`)** | 54 bytes | **18 bytes:** `MSG\|12.4\|18.1\|100\|` | **Hasta 36 bytes** | **1 trama** (mensaje directo sin fragmentar) |
| **Fragmentada (`MSGP`)** | 54 bytes | **26 bytes:** `MSGP\|12.4\|18.1\|100\|` (19 B) + `id.k.n:` (7 B) | **28 bytes** (`BYTES_FRAGMENTO`) | **2 a 5 tramas** según el largo real |

**Cálculo real de fragmentos:**
- Con 1 fragmento: hasta 28 bytes de texto.
- Con 2 fragmentos: hasta 56 bytes de texto (ej. un reporte de 50 bytes usa solo 2 tramas).
- Con 3 fragmentos: hasta 84 bytes de texto.
- Con 4 fragmentos: hasta 112 bytes de texto.
- Con **5 fragmentos**: hasta **140 bytes de capacidad** ($5 \times 28$), lo que cubre con total holgura el límite de **120 bytes** (`MAX_TEXTO_LARGO`), incluso con caracteres UTF-8 multibyte (tildes, eñes).

> **Dinámico y sin relleno:** Si un usuario envía un mensaje de 50 bytes, el firmware calcula automáticamente $n=2$ partes. Se envían únicamente 2 tramas en el aire; **no se hace relleno (*padding*) artificial** ni se envían tramas vacías.

### Tiempo en el aire (Time on Air a 9,6 kbps FSK)

| Componente de la trama | Tamaño / Duración |
|---|---|
| Preámbulo + Sync words (0x2D, 0xD4) | 6 bytes (48 bits) ≈ **5,0 ms** |
| Paquete RF completo (datos + cabeceras + CRC) | Hasta 58-60 bytes ≈ **48,3 ms** |
| Cifrado AES-128 por hardware (4 bloques) | **~28 µs** (despreciable frente al aire) |
| Arranque del transmisor (PLL lock + PA ramp) | **< 1 ms** |
| **Tiempo total en el aire por trama (ToA)** | **~54 a 57 ms** |
| **Ciclo completo con confirmación (ACK de RHMesh)** | **~100 a 150 ms por salto (hop)** |

### ¿Cada cuánto se puede enviar un mensaje por el chat de la app?

Al ser una red en malla half-duplex sobre un canal compartido en 915 MHz:

- **Mensaje corto (≤ 36 bytes / 1 trama):** cada **1 a 2 segundos** como máximo sostenible por nodo.
- **Mensaje largo (37 a 120 bytes / 2 a 5 tramas):** cada **4 a 6 segundos**, para dar tiempo a que cada fragmento sea confirmado por la malla y evitar saturar el canal.
- **Telemetría de energía (`TEL`):** cada **5 minutos** (`INTERVALO_TEL_MS`). Batería y panel tienen inercia lenta; reportar más rápido desperdiciaría energía y canal.
- **Posición GPS (`POS`):** cada **30 a 60 segundos** en brigadas móviles; cada 30 minutos en albergues fijos.

> **Regla de oro de la malla:** Si hay 5 a 10 nodos operando en el territorio, el intervalo de chat entre mensajes de un mismo nodo debe mantenerse en **al menos 5 segundos** para evitar colisiones y pérdida de fragmentos.

## Usuarios y sesiones

Todo el API (salvo `/api/auth/login`, `/api/config` y la descarga de la app) pide una sesión. Al
arrancar por primera vez se crea `admin` con el PIN de `ADMIN_PIN` (por defecto `1234`). Roles,
permisos y API: [USUARIOS.md](../USUARIOS.md). Las pruebas (`tests/test_auth.py`) necesitan
`pip install -r requirements-dev.txt`.

## Gateways y enlaces

- Tabla **`gateways`**: un registro por gateway (`gw-1`, `gw-2`…) con nombre, dirección en la malla,
  conexión (`usb:COM5`, `sim`), estado (`conectado`/`desconectado`), energía y última vez escuchado.
  El listener envía un latido por minuto; si un gateway calla 2,5 min se marca desconectado y se crea
  una alerta `gateway_desconectado`.
- Tabla **`enlaces`**: (nodo, gateway) → última señal, promedio móvil, tramas y última vez. Se usa para
  responder por el mejor gateway, ver qué nodos dependen de uno solo y dibujar la red.
- `messages.gateway_id`: por qué gateway entró cada mensaje. Si la misma trama llega por dos gateways
  en menos de 30 s, se guarda una sola vez.
- API: `GET /api/gateways` (con los enlaces de cada uno) y `GET /api/enlaces`.
- Varios gateways USB: `MESH_USB_DEVICE=COM5,COM7` y nombres opcionales en `MESH_GATEWAY_NAMES`.
  El simulador crea 2 gateways (`SIM_GATEWAYS`).

## Gestión de alertas y reportes

- Cada alerta (mensaje crítico, zona de riesgo, batería baja) se guarda en la tabla `alerts` con
  estado `nueva` → `en_atencion` → `atendida`, equipo asignado y nota.
- API: `GET /api/alerts` y `PATCH /api/alerts/{id}` con `{"estado","equipo","nota"}`; los cambios se
  publican en `events/alert_update` y se ven en vivo en el dashboard y en la app.
- Exportar: `GET /api/export/mensajes.csv` y `GET /api/export/alertas.csv` (enlaces en el dashboard).

## Energía

`NODE_BATTERY_WH` (77) y `NODE_CONSUMPTION_W` (0,54) describen el kit de cada nodo
([ENERGIA.md](../ENERGIA.md)); con ellos el dashboard y la app estiman la autonomía sin sol.
`LOW_BATTERY_PCT` (20) fija el umbral de la alerta de batería baja.

## Escenario de demo

`MESH_CONNECTION=escenario` (o `iniciar.ps1 -Radio escenario`) reproduce un sismo guionizado y luego
sigue con la simulación normal. Guion en [DEMO.md](../DEMO.md).

## Descarga de la app sin internet

El dashboard sirve la página de descarga en `/descargar` y el APK en `/descargar/RedEmergencia.apk`. Antes del evento, copiar el APK a `server/descargas/` (ver `descargas/LEEME.md`). Los teléfonos conectados al Wi‑Fi del puesto de mando instalan la app abriendo `http://192.168.1.10:8080/descargar`. La página funciona aunque el broker MQTT esté apagado.

## Mapa offline

Por defecto el mapa usa mosaicos de OpenStreetMap **en línea**. Para operar sin internet:

1. Antes del evento, descargar los mosaicos de Manizales (zoom 12–17) a un archivo `.mbtiles`, por ejemplo con QGIS (*Generar mosaicos XYZ*) o con MOBAC.
2. Servirlos en la red local con un servidor de mosaicos (p. ej. `tileserver-gl-light`) y apuntar `TILE_URL` a él, p. ej. `TILE_URL=http://192.168.1.10:8081/{z}/{x}/{y}.png`.

Sin mosaicos el mapa sigue funcionando (nodos, recorridos y zonas se ven sobre fondo gris).

## Zonas de riesgo

`zones/zonas_riesgo.geojson` trae **dos polígonos de ejemplo** para la demo. Reemplazarlos por la cartografía oficial de amenaza por deslizamiento (POT de Manizales / Unidad de Gestión del Riesgo). Se puede editar en <https://geojson.io> o en QGIS.

## Seguridad

- Mosquitto solo escucha en `127.0.0.1`; el único puerto expuesto a la LAN es el dashboard (8080).
- El dashboard no tiene autenticación: está pensado para la red cerrada del puesto de mando. Si la red Wi‑Fi del puesto es abierta, agregar autenticación o un proxy con contraseña.
- Los contenedores corren con un usuario sin privilegios.
- El cifrado AES-128 del RFM69HCW protege las tramas por aire; la clave debe ser idéntica en todos los nodos y el gateway.
