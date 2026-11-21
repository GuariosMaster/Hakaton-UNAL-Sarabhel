# Servidor local de mensajería de emergencia — Equipo Sarabhel

Servidor del puesto de mando que recibe los mensajes de la red Meshtastic (LoRa),
los clasifica por prioridad, rastrea la ubicación GPS de los nodos y los muestra en
un mapa web. Funciona **sin internet** y está pensado para correr en un portátil
alimentado por batería o panel solar.

## Arquitectura

```
 Nodos LoRa (Meshtastic) ──radio──► Gateway ──USB/serie o Wi-Fi──► Listener
                                                                     │
                                                         Mosquitto (MQTT, pub/sub)
                                    ┌────────────────────────┼────────────────────────┐
                              Mensajería               Localización                Dashboard
                      (prioridad, buzón, envío)  (GPS, historial, geocercas)  (API + mapa en vivo)
                                    └──────────────► SQLite (WAL) ◄───────────────────┘
```

| Servicio | Archivo | Qué hace |
|---|---|---|
| **Broker** | `mosquitto/mosquitto.conf` | Mosquitto: bus publicación/suscripción con persistencia (QoS 1). |
| **Listener** | `sarabhel/listener.py` | Lee el gateway (serie, TCP o simulado), traduce paquetes a JSON y los publica. Transmite por radio lo que llega a `lora/gateway/tx`. |
| **Mensajería** | `sarabhel/messaging.py` | Clasifica (crítico / moderado / informativo), adjunta la última posición del remitente, guarda y emite alertas. |
| **Localización** | `sarabhel/location.py` | Guarda posiciones GPS e historial, nombre y batería de cada nodo, detecta entrada a zonas de riesgo. |
| **Dashboard** | `sarabhel/dashboard.py` + `static/` | API REST, eventos en vivo (SSE) y mapa Leaflet incluido localmente (no usa CDN). |

### ¿Por qué no Kubernetes?
Un clúster de Kubernetes (aunque sea k3s) consume entre 0,5 y 1 GB de RAM y CPU
constante en el plano de control, lo que reduce la autonomía de la batería y agrega
piezas que pueden fallar. Con Docker Compose y procesos Python conservamos el mismo
diseño de microservicios desacoplados por un broker, pero con unos cientos de MB en
total y un solo comando para levantar o reiniciar todo.

### Temas MQTT

| Tema | Publica | Contenido |
|---|---|---|
| `lora/gateway/rx/text` · `/position` · `/nodeinfo` · `/telemetry` | listener | Paquete de radio en JSON |
| `lora/gateway/tx` | mensajería | `{text, to}` para transmitir |
| `lora/nodes` | localización | Estado de un nodo ya guardado |
| `app/send` | dashboard | Mensaje escrito en el puesto de mando |
| `events/msg` · `events/position` · `events/alert` | servicios | Datos ya procesados y guardados |

Los mensajes entrantes se deduplican por `packet_id` de Meshtastic, así que un reintento de la malla no genera dos registros. El dashboard muestra una banda **DEMO** cuando el listener corre en modo simulado; en modo `serial`/`tcp` los nodos y telemetría son los que reporta el gateway.

## Puesta en marcha

### A) Servidor Ubuntu con Docker (despliegue final)

```bash
cp .env.example .env
# Demo sin radio (la interfaz marca los datos como DEMO):
docker compose up -d --build
# Gateway RAK conectado por USB (en este puesto: /dev/ttyACM0):
docker compose -f docker-compose.yml -f docker-compose.serial.yml up -d --build
# Si el puerto aparece con otro nombre o el grupo cambia:
MESH_SERIAL_DEVICE=/dev/ttyACM0 MESH_SERIAL_GID=$(stat -c %g /dev/ttyACM0) \
  docker compose -f docker-compose.yml -f docker-compose.serial.yml up -d --build
# Gateway por Wi-Fi:
MESH_CONNECTION=tcp MESH_TCP_HOST=192.168.4.1 docker compose up -d --build
```

El puerto USB solo lo abre el listener. Si `docker compose logs listener` muestra error de
permisos, revisar `MESH_SERIAL_GID` con `stat -c %g /dev/ttyACM0`. Mosquitto no publica
ningún puerto al host: solo existe dentro de la red de Compose.

Abrir `http://<ip-del-servidor>:8080` desde cualquier equipo de la red local.
Ver los registros: `docker compose logs -f listener mensajeria`.

### B) Windows sin Docker (desarrollo / demo en el portátil)

Docker Desktop en Windows **no puede pasar puertos COM** al contenedor, así que en
Windows se ejecuta todo con Python. Se necesita un broker MQTT: instalar
[Mosquitto para Windows](https://mosquitto.org/download/), o para pruebas instalar
`amqtt` (pure Python) junto con los requisitos del paso siguiente.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt amqtt
# Cada uno en su propia terminal:
.venv\Scripts\amqtt
.venv\Scripts\python -m sarabhel.messaging
.venv\Scripts\python -m sarabhel.location
.venv\Scripts\python -m sarabhel.dashboard
$env:MESH_CONNECTION="serial"; $env:MESH_SERIAL_PORT="COM5"; .venv\Scripts\python -m sarabhel.listener
```

Sin `MESH_CONNECTION` el listener arranca en **modo simulado**: 5 nodos ficticios en
Manizales que envían posiciones, mensajes (incluidos SOS) y batería.

### Pruebas

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

Desde la raíz del repositorio: `python3 -m unittest discover -s server/tests -v`.
Las pruebas usan solo la biblioteca estándar: no requieren pytest ni un broker MQTT.

## Configuración del nodo Meshtastic

Para que el gateway entregue los paquetes al servidor y no salgan a internet:

- `module_config.mqtt.enabled: false` en cada nodo (ver `../config/meshtastic.example.yaml`: así el gateway
  entrega los paquetes al Listener por USB y no los publica en la nube). Nunca versionar `config.yaml`,
  porque puede contener claves.
- `config.position.gpsMode: ENABLED` en los nodos con GPS; en los demás, compartir el GPS del celular desde la app.
  Un nodo sin posición aparece en la lista como «sin GPS», sin coordenadas inventadas.
- Mensajes rápidos (`canned_messages`) de emergencia, por ejemplo:
  `SOS|Herido|Atrapado|Necesito agua|Necesito medicina|Estoy bien|Evacuando`.
- Mantener `bluetooth.mode: RANDOM_PIN` (la referencia ya no usa el PIN fijo `123456`) y regenerar
  las claves si un `config.yaml` llegó a compartirse. La región de Colombia es `ANZ`.

## Mapa offline

Por defecto el mapa usa mosaicos de OpenStreetMap **en línea**. Para operar sin internet:

1. Antes del evento, descargar los mosaicos de Manizales (zoom 12–17) a un archivo
   `.mbtiles`, por ejemplo con QGIS (*Generar mosaicos XYZ*) o con MOBAC.
2. Servirlos en la red local con un servidor de mosaicos (p. ej. `tileserver-gl-light`)
   y apuntar `TILE_URL` a él, p. ej. `TILE_URL=http://192.168.1.10:8081/{z}/{x}/{y}.png`.

Sin mosaicos el mapa sigue funcionando (nodos, recorridos y zonas se ven sobre fondo gris).

## Zonas de riesgo

`zones/zonas_riesgo.geojson` trae **dos polígonos de ejemplo** para la demo. Reemplazarlos
por la cartografía oficial de amenaza por deslizamiento (POT de Manizales / Unidad de
Gestión del Riesgo). Se puede editar en <https://geojson.io> o en QGIS.

## Seguridad

- Mosquitto no expone puertos al host; el único puerto publicado es el dashboard (8080).
- El dashboard no tiene autenticación: está pensado para la red cerrada del puesto de mando.
  Si la red Wi-Fi del puesto es abierta, agregar autenticación o un proxy con contraseña.
- Los contenedores corren con un usuario sin privilegios.
