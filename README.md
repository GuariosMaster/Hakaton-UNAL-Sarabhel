# Red de emergencia FSK 915 MHz — Equipo Sarabhel

Cuando cae la red eléctrica y la red celular, la coordinación se cae con ella. Este prototipo propone lo contrario: una red de comunicaciones autónoma en la banda sub-GHz de **915,0 MHz** con modulación **FSK**, que sigue funcionando sin internet, sin torres celulares y sin SIM, y devuelve visibilidad al Puesto de Mando Unificado (PMU) justo cuando más se necesita.

La capa de radio se basa en transceptores **RFM69HCW** ($+20\ \text{dBm}$, cifrado **AES-128** por hardware) sobre placas **ESP32 / ESP32-S3 / ESP32-C6**, con enrutamiento en malla mediante **RadioHead RHMesh**. La innovación está en lo que construimos encima:

- un **tablero local de energía y alertas** para el puesto de mando, con telemetría de micro-redes solares (voltaje de batería, panel solar, nivel de carga);
- un **servidor local de mensajería crítica** (Python + Mosquitto MQTT + SQLite) que recibe, organiza y consulta los mensajes de la malla FSK;
- un **portal Wi-Fi local sin internet** en cada nodo de albergue, para que los brigadistas envíen reportes de texto desde cualquier teléfono sin instalar apps.

El resultado buscado no es solo que los nodos se hablen: es que esa información llegue a quien decide en el territorio, incluso cuando no hay señal ni electricidad.

## Estructura del repositorio

| Carpeta | Contenido |
|---|---|
| [`app/`](app/) | **App móvil Android propia** con dos modos: *Campo* (portal Wi-Fi local del nodo, botón SOS con GPS, chat) y *Puesto de mando* (alertas, mapa y mensajes desde el servidor por Wi‑Fi local). Ver [app/README.md](app/README.md). |
| [`web/`](web/) | Página de descarga de la app. Servida por el servidor local en `/descargar` (descarga sin internet). |
| [`server/`](server/) | Servidor local del puesto de mando: Mosquitto (MQTT) + servicios Python (listener USB del gateway ESP32-S3, mensajería, localización GPS, dashboard con mapa) + SQLite, orquestado con Docker Compose. Ver [server/README.md](server/README.md). |
| [`config/`](config/) | Configuración de referencia de los nodos RFM69HCW / ESP32 (parámetros FSK, claves AES, pines SPI). |

## Descargar la app

- **Con internet:** https://guariosmaster.github.io/Lora-Hakaton/ — el APK se compila automáticamente con GitHub Actions en cada cambio de `app/` y queda en la release [`apk-latest`](https://github.com/GuariosMaster/Lora-Hakaton/releases/tag/apk-latest).
- **Sin internet, en el puesto de mando:** conectarse al Wi‑Fi del portátil y abrir `http://192.168.137.1:8080/descargar` (copiar antes el APK a `server/descargas/`).

## Probar la app entre teléfonos

Sin hardware RF, el servidor del portátil reparte los mensajes entre los teléfonos conectados a su Wi‑Fi (conexión **📶 Red local** de la app). Guía paso a paso en [PRUEBAS.md](PRUEBAS.md).

## Probar sin hardware RF

El listener incluye un modo simulado que emula nodos FSK 915 MHz en Manizales:

```bash
cd server
docker compose up -d --build
# abrir http://localhost:8080
```

## Estado del proyecto

> **Nota (noviembre 2026):** el software del servidor está funcionando y probado en **modo simulado**. Aún no tenemos el dispositivo físico (nodos ESP32 + RFM69HCW y gateway ESP32-S3), por lo que nada se ha probado todavía con radio real FSK.

### Lo que ya está hecho

- [x] **Arquitectura liviana**: Docker Compose + Mosquitto (MQTT) + servicios Python + SQLite, en lugar de Kubernetes, para ahorrar RAM, CPU y batería en el puesto de mando.
- [x] **Listener USB** que lee JSON del gateway ESP32-S3 + RFM69HCW por puerto serie nativo (CDC) a 115.200 baudios, con **modo simulado** de nodos ficticios en Manizales para demos sin hardware.
- [x] **Servicio de mensajería**: guarda el historial y clasifica cada mensaje como crítico, moderado o informativo por palabras clave (SOS, herido, agua…).
- [x] **Servicio de localización GPS**: última posición e historial de cada nodo, batería, y alerta cuando un nodo entra en una zona de riesgo (geocercas).
- [x] **Dashboard web** del puesto de mando: mapa en vivo, alertas, lista de nodos, recorrido de cada nodo y envío de mensajes a la red.
- [x] Configuración de referencia de los nodos RFM69HCW (sin claves expuestas).
- [x] Pruebas unitarias (prioridad, paquetes, geocercas).
- [x] **App móvil Android** (React + Capacitor) con modo Campo (portal Wi-Fi del nodo, SOS con GPS del teléfono, mensajes rápidos, chat, mapa) y modo Puesto de mando (alertas, mapa, mensajes). Probada en el navegador con radio simulada y con el servidor.

### Lo que falta

**Necesita el dispositivo físico**
- [ ] Probar el listener USB con el gateway ESP32-S3 + RFM69HCW real.
- [ ] Probar la app móvil por el portal Wi-Fi local del nodo con hardware real e instalar el APK en varios teléfonos.
- [ ] Aplicar la configuración FSK 915 MHz a los nodos (frecuencia, potencia, sync word, clave AES).
- [ ] Pruebas de enlace RF en Manizales (distancia, RSSI, tasa de entrega, consumo energético).
- [ ] Probar el despliegue con Docker en el servidor Ubuntu del PMU.

**Se puede avanzar sin hardware**
- [ ] **Gestión de alertas**: marcar una alerta como atendida, asignar equipo de rescate y agregar notas.
- [ ] **Kit de energía**: dimensionar panel, batería y autonomía (nodos y servidor) y mostrarlo en el dashboard.
- [ ] **Escenario de demo guionizado** (un "sismo" simulado que siempre se desarrolla igual).
- [ ] **Confirmación de entrega y buzón** para nodos desconectados.
- [ ] **Mapa offline** de Manizales (mosaicos servidos en local; hoy el mapa usa internet).
- [ ] **Zonas de riesgo oficiales** (POT / Corpocaldas); las actuales son polígonos de ejemplo.
- [ ] Estadísticas y exportación de reportes (CSV).
- [ ] Contraseña de acceso al dashboard.

**Documentación**
- [ ] Unificar las propuestas técnicas en un solo documento alineado con lo construido (ver borrador `add_fsk_v1.md` en la raíz del proyecto).
- [ ] Definir hardware: placas ESP32-S3, ESP32 DevKit V1, ESP32-C6, transceptores RFM69HCW 915 MHz, paneles solares y baterías LiFePO4.
