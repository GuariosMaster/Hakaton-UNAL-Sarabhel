# Servidor local de mensajería de emergencia — Equipo Sarabhel

Servidor del puesto de mando que recibe los mensajes de la red **FSK 915 MHz** (transceptores RFM69HCW, gateway ESP32-S3 por USB nativo), los clasifica por prioridad, rastrea la ubicación GPS de los nodos y los muestra en un mapa web. Funciona **sin internet** y está pensado para correr en un portátil alimentado por batería o panel solar.

## Arquitectura

```
 Nodos FSK 915 MHz (RFM69HCW + ESP32) ──radio──► Gateway ESP32-S3 ──USB CDC──► Listener
                                                                               │
                                                         Mosquitto (MQTT, pub/sub)
                                    ┌────────────────────────┼────────────────────────┐
                              Mensajería               Localización                Dashboard
                      (prioridad, buzón, envío)  (GPS, historial, geocercas)  (API + mapa en vivo)
                                    └──────────────► SQLite (WAL) ◄───────────────────┘
```

| Servicio | Archivo | Qué hace |
|---|---|---|
<<<<<<< HEAD
| **Broker** | Mosquitto | Bus publicación/suscripción con persistencia (QoS 1). |
| **Listener** | `sarabhel/listener.py` | Lee el gateway ESP32-S3 por USB serial (pyserial, 115.200 baudios), traduce cada trama JSON a eventos y los publica en Mosquitto. Escribe en el gateway los mensajes de `red/tx/msg` para transmitirlos por radio. |
| **Mensajería** | `sarabhel/messaging.py` | Clasifica (crítico / moderado / informativo), adjunta la última posición del remitente, guarda en SQLite y emite alertas. |
| **Localización** | `sarabhel/location.py` | Guarda posiciones GPS e historial, nombre y energía de cada nodo (batería V, panel V, % carga), detecta entrada a zonas de riesgo y alerta de batería baja. |
=======
| **Broker** | `mosquitto/mosquitto.conf` | Mosquitto: bus publicación/suscripción con persistencia (QoS 1). |
| **Listener** | `sarabhel/listener.py` | Lee el gateway (serie, TCP o simulado), traduce paquetes a JSON y los publica. Transmite por radio lo que llega a `lora/gateway/tx`. |
| **Mensajería** | `sarabhel/messaging.py` | Clasifica (crítico / moderado / informativo), adjunta la última posición del remitente, guarda y emite alertas. |
| **Localización** | `sarabhel/location.py` | Guarda posiciones GPS e historial, nombre y batería de cada nodo, detecta entrada a zonas de riesgo. |
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9
| **Dashboard** | `sarabhel/dashboard.py` + `static/` | API REST, eventos en vivo (SSE) y mapa Leaflet incluido localmente (no usa CDN). |

### ¿Por qué no Kubernetes?
Un clúster de Kubernetes (aunque sea k3s) consume entre 0,5 y 1 GB de RAM y CPU constante en el plano de control, lo que reduce la autonomía de la batería y agrega piezas que pueden fallar. Con Docker Compose y procesos Python conservamos el mismo diseño de microservicios desacoplados por un broker, pero con unos cientos de MB en total y un solo comando para levantar o reiniciar todo.

### Temas MQTT

| Tema | Publica | Contenido |
|---|---|---|
<<<<<<< HEAD
| `red/albergue/{nodo_id}/msg` | listener | Mensaje de texto recibido por RF FSK |
| `red/albergue/{nodo_id}/tel` | listener | Telemetría energética (batería, panel, carga) |
| `red/albergue/{nodo_id}/pos` | listener | Posición GPS del nodo |
| `red/albergue/{nodo_id}/info` | listener | Nombre del nodo |
| `app/send` | dashboard | Mensaje escrito en el puesto de mando (lo guarda el servicio de mensajería) |
| `red/tx/msg` | mensajería | Mensaje a transmitir por radio: `{text, to}` → el listener lo escribe en el gateway |

`{nodo_id}` es `nodo-N` para los nodos de radio (dirección RHMesh N) o `!xxxxxxxx` para los teléfonos
conectados por Wi‑Fi al puesto de mando (endpoints `/api/device/*`).
| `events/msg` · `events/position` · `events/node` · `events/alert` | servicios | Datos ya procesados y guardados |
=======
| `lora/gateway/rx/text` · `/position` · `/nodeinfo` · `/telemetry` | listener | Paquete de radio en JSON |
| `lora/gateway/tx` | mensajería | `{text, to}` para transmitir |
| `lora/nodes` | localización | Estado de un nodo ya guardado |
| `app/send` | dashboard | Mensaje escrito en el puesto de mando |
| `events/msg` · `events/position` · `events/alert` | servicios | Datos ya procesados y guardados |

Los mensajes entrantes se deduplican por `packet_id` de Meshtastic, así que un reintento de la malla no genera dos registros. El dashboard muestra una banda **DEMO** cuando el listener corre en modo simulado; en modo `serial`/`tcp` los nodos y telemetría son los que reporta el gateway.
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9

## Puesta en marcha

### A) Servidor Ubuntu con Docker (despliegue final)

```bash
cp .env.example .env
<<<<<<< HEAD
# Demo sin hardware RF (modo simulado):
docker compose up -d --build
# Gateway ESP32-S3 conectado por USB nativo (aparece como /dev/ttyACM0):
MESH_USB_DEVICE=/dev/ttyACM0 docker compose -f docker-compose.yml -f docker-compose.serial.yml up -d --build
# Variables relevantes: MESH_CONNECTION=usb, MESH_USB_DEVICE, MESH_USB_BAUD=115200
=======
# Demo sin radio (la interfaz marca los datos como DEMO):
docker compose up -d --build
# Gateway RAK conectado por USB (en este puesto: /dev/ttyACM0):
docker compose -f docker-compose.yml -f docker-compose.serial.yml up -d --build
# Si el puerto aparece con otro nombre o el grupo cambia:
MESH_SERIAL_DEVICE=/dev/ttyACM0 MESH_SERIAL_GID=$(stat -c %g /dev/ttyACM0) \
  docker compose -f docker-compose.yml -f docker-compose.serial.yml up -d --build
# Gateway por Wi-Fi:
MESH_CONNECTION=tcp MESH_TCP_HOST=192.168.4.1 docker compose up -d --build
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9
```

El puerto USB solo lo abre el listener. Si `docker compose logs listener` muestra error de
permisos, revisar `MESH_SERIAL_GID` con `stat -c %g /dev/ttyACM0`. Mosquitto no publica
ningún puerto al host: solo existe dentro de la red de Compose.

Abrir `http://<ip-del-servidor>:8080` desde cualquier equipo de la red local.
Ver los registros: `docker compose logs -f listener mensajeria`.

<<<<<<< HEAD
### B) Windows sin Docker (demo en el portátil)
=======
### B) Windows sin Docker (desarrollo / demo en el portátil)

Docker Desktop en Windows **no puede pasar puertos COM** al contenedor, así que en
Windows se ejecuta todo con Python. Se necesita un broker MQTT: instalar
[Mosquitto para Windows](https://mosquitto.org/download/), o para pruebas instalar
`amqtt` (pure Python) junto con los requisitos del paso siguiente.
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9

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

<<<<<<< HEAD
```bash
.venv/bin/python -m pytest -q tests
```

## Configuración de los nodos RFM69HCW
=======
```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

Desde la raíz del repositorio: `python3 -m unittest discover -s server/tests -v`.
Las pruebas usan solo la biblioteca estándar: no requieren pytest ni un broker MQTT.

## Configuración del nodo Meshtastic
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9

El firmware está en [`firmware/`](../firmware/) y los parámetros en [`firmware/include/config.h`](../firmware/include/config.h). Cada nodo (ESP32 + RFM69HCW) y el gateway (ESP32-S3 + RFM69HCW) deben compartir los mismos parámetros RF:

<<<<<<< HEAD
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
=======
- `module_config.mqtt.enabled: false` en cada nodo (ver `../config/meshtastic.example.yaml`: así el gateway
  entrega los paquetes al Listener por USB y no los publica en la nube). Nunca versionar `config.yaml`,
  porque puede contener claves.
- `config.position.gpsMode: ENABLED` en los nodos con GPS; en los demás, compartir el GPS del celular desde la app.
  Un nodo sin posición aparece en la lista como «sin GPS», sin coordenadas inventadas.
- Mensajes rápidos (`canned_messages`) de emergencia, por ejemplo:
  `SOS|Herido|Atrapado|Necesito agua|Necesito medicina|Estoy bien|Evacuando`.
- Mantener `bluetooth.mode: RANDOM_PIN` (la referencia ya no usa el PIN fijo `123456`) y regenerar
  las claves si un `config.yaml` llegó a compartirse. La región de Colombia es `ANZ`.
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9

## Mapa offline

Por defecto el mapa usa mosaicos de OpenStreetMap **en línea**. Para operar sin internet:

1. Antes del evento, descargar los mosaicos de Manizales (zoom 12–17) a un archivo `.mbtiles`, por ejemplo con QGIS (*Generar mosaicos XYZ*) o con MOBAC.
2. Servirlos en la red local con un servidor de mosaicos (p. ej. `tileserver-gl-light`) y apuntar `TILE_URL` a él, p. ej. `TILE_URL=http://192.168.1.10:8081/{z}/{x}/{y}.png`.

Sin mosaicos el mapa sigue funcionando (nodos, recorridos y zonas se ven sobre fondo gris).

## Zonas de riesgo

`zones/zonas_riesgo.geojson` trae **dos polígonos de ejemplo** para la demo. Reemplazarlos por la cartografía oficial de amenaza por deslizamiento (POT de Manizales / Unidad de Gestión del Riesgo). Se puede editar en <https://geojson.io> o en QGIS.

## Seguridad

<<<<<<< HEAD
- Mosquitto solo escucha en `127.0.0.1`; el único puerto expuesto a la LAN es el dashboard (8080).
- El dashboard no tiene autenticación: está pensado para la red cerrada del puesto de mando. Si la red Wi‑Fi del puesto es abierta, agregar autenticación o un proxy con contraseña.
=======
- Mosquitto no expone puertos al host; el único puerto publicado es el dashboard (8080).
- El dashboard no tiene autenticación: está pensado para la red cerrada del puesto de mando.
  Si la red Wi-Fi del puesto es abierta, agregar autenticación o un proxy con contraseña.
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9
- Los contenedores corren con un usuario sin privilegios.
- El cifrado AES-128 del RFM69HCW protege las tramas por aire; la clave debe ser idéntica en todos los nodos y el gateway.
