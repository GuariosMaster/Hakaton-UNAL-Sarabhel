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
| **Broker** | Mosquitto | Bus publicación/suscripción con persistencia (QoS 1). |
| **Listener** | `sarabhel/listener.py` | Lee el gateway ESP32-S3 por USB serial (pyserial, 115.200 baudios), traduce cada trama JSON a eventos y los publica en Mosquitto. Recibe mensajes para transmitir por radio desde `app/send`. |
| **Mensajería** | `sarabhel/messaging.py` | Clasifica (crítico / moderado / informativo), adjunta la última posición del remitente, guarda en SQLite y emite alertas. |
| **Localización** | `sarabhel/location.py` | Guarda posiciones GPS e historial, nombre y batería de cada nodo, detecta entrada a zonas de riesgo. |
| **Dashboard** | `sarabhel/dashboard.py` + `static/` | API REST, eventos en vivo (SSE) y mapa Leaflet incluido localmente (no usa CDN). |

### ¿Por qué no Kubernetes?
Un clúster de Kubernetes (aunque sea k3s) consume entre 0,5 y 1 GB de RAM y CPU constante en el plano de control, lo que reduce la autonomía de la batería y agrega piezas que pueden fallar. Con Docker Compose y procesos Python conservamos el mismo diseño de microservicios desacoplados por un broker, pero con unos cientos de MB en total y un solo comando para levantar o reiniciar todo.

### Temas MQTT (según borrador `add_fsk_v1.md`)

| Tema | Publica | Contenido |
|---|---|---|
| `red/albergue/{nodo_id}/msg` | listener | Mensaje de texto recibido por RF FSK |
| `red/albergue/{nodo_id}/tel` | listener | Telemetría energética (batería, panel, carga) |
| `red/albergue/{nodo_id}/pos` | listener | Posición GPS del nodo |
| `app/send` | dashboard | Mensaje escrito en el puesto de mando para transmitir por radio |
| `events/msg` · `events/position` · `events/node` · `events/alert` | servicios | Datos ya procesados y guardados |

## Puesta en marcha

### A) Servidor Ubuntu con Docker (despliegue final)

```bash
cp .env.example .env
# Demo sin hardware RF (modo simulado):
docker compose up -d --build
# Gateway ESP32-S3 conectado por USB nativo:
docker compose up -d --build
# Variables relevantes: MESH_CONNECTION=usb, MESH_USB_DEVICE=/dev/ttyUSB0, MESH_USB_BAUD=115200
```

Abrir `http://<ip-del-servidor>:8080` desde cualquier equipo de la red local.
Ver los registros: `docker compose logs -f listener mensajeria`.

### B) Sin Docker (desarrollo / demo en el portátil)

Se necesita un broker MQTT: instalar Mosquitto, o para pruebas usar `amqtt` (pure Python).

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt amqtt pyserial
# Cada uno en su propia terminal:
.venv/bin/amqtt
.venv/bin/python -m sarabhel.messaging
.venv/bin/python -m sarabhel.location
.venv/bin/python -m sarabhel.dashboard
# Modo simulado (sin hardware):
MESH_CONNECTION=sim .venv/bin/python -m sarabhel.listener
# Con gateway ESP32-S3 por USB:
MESH_CONNECTION=usb MESH_USB_DEVICE=/dev/ttyUSB0 MESH_USB_BAUD=115200 .venv/bin/python -m sarabhel.listener
```

Sin `MESH_CONNECTION` el listener arranca en **modo simulado**: nodos ficticios FSK en Manizales que envían posiciones, mensajes (incluidos SOS) y telemetría energética.

### Pruebas

```bash
.venv/bin/python -m pytest -q tests
```

## Configuración de los nodos RFM69HCW

Cada nodo (ESP32 + RFM69HCW) y el gateway (ESP32-S3 + RFM69HCW) deben compartir los mismos parámetros RF:

| Parámetro | Valor | Justificación |
|---|---|---|
| Frecuencia portadora | 915,0 MHz | Banda ISM libre en Colombia |
| Modulación | FSK (`FSK_Rb9_6Fd19_2`) | 9,6 kbps, baja tiempo en el aire (~42 ms por paquete de 50 bytes) |
| Potencia TX | +20 dBm | Máxima del RFM69HCW |
| Protocolo malla | RadioHead RHMesh | Enrutamiento multi-salto, ACK, direccionamiento ID 1-254 |
| Cifrado | AES-128 por hardware | Sin carga extra en el ESP32 |
| Sync Word | 0x2D, 0xD4 | Filtrado de ruido en 915 MHz |
| Trama por aire | `TIPO|BAT_V|PANEL_V|CARGA_PCT|MENSAJE` | Ej: `MSG|12.4|18.1|82|Albergue Coliseo: 280 personas, sin red` |
| USB Serial (gateway → PC) | JSON a 115.200 baudios | Ej: `{"nodo":2,"tipo":"MSG","bat":12.4,"panel":18.1,"carga":82,"msg":"...","rssi":-72}` |

## Descarga de la app sin internet

El dashboard sirve la página de descarga en `/descargar` y el APK en `/descargar/RedEmergenciaLoRa.apk`. Antes del evento, copiar el APK a `server/descargas/` (ver `descargas/LEEME.md`). Los teléfonos conectados al Wi‑Fi del puesto de mando instalan la app abriendo `http://192.168.1.10:8080/descargar`. La página funciona aunque el broker MQTT esté apagado.

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
