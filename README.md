# Red de emergencia FSK 915 MHz — Equipo Sarabhel

Cuando cae la red eléctrica y la red celular, la coordinación se cae con ella. Este prototipo propone lo contrario: una red de comunicaciones autónoma en la banda sub-GHz de **915,0 MHz** con modulación **FSK**, que sigue funcionando sin internet, sin torres celulares y sin SIM, y devuelve visibilidad al Puesto de Mando Unificado (PMU) justo cuando más se necesita.

La capa de radio se basa en transceptores **RFM69HCW** ($+20\ \text{dBm}$, cifrado **AES-128** por hardware) sobre placas **ESP32 / ESP32-S3 / ESP32-C6**, con enrutamiento en malla mediante **RadioHead RHMesh**. La innovación está en lo que construimos encima:

- un **tablero local de energía y alertas** para el puesto de mando, con telemetría de micro-redes solares (voltaje de batería, panel solar, nivel de carga);
- un **servidor local de mensajería crítica** (Python + Mosquitto MQTT + SQLite) que recibe, organiza y consulta los mensajes de la malla FSK;
- un **motor de triaje inteligente con IA local (Edge LLM)**: Ollama (`qwen2.5:1.5b`) operando 100% offline, clasificando reportes bajo la taxonomía estándar **EDAN** (Evaluación de Daños y Análisis de Necesidades), extrayendo necesidades tácticas (ambulancias, agua, herramientas) y resúmenes ejecutivos;
- un **portal Wi-Fi local sin internet** en cada nodo de albergue, para que los brigadistas envíen reportes de texto desde cualquier teléfono sin instalar apps.

El resultado buscado no es solo que los nodos se hablen: es que esa información llegue a quien decide en el territorio, incluso cuando no hay señal ni electricidad.

## Estructura del repositorio

| Carpeta | Contenido |
|---|---|
| [`app/`](app/) | **App móvil Android propia** con dos modos: *Campo* (portal Wi-Fi local del nodo, botón SOS con GPS, chat) y *Puesto de mando* (alertas, mapa, mensajes y triaje EDAN en vivo desde el servidor por Wi‑Fi local). Ver [app/README.md](app/README.md). |
| [`web/`](web/) | Página de descarga de la app. Servida por el servidor local en `/descargar` (descarga sin internet). |
| [`server/`](server/) | Servidor local del puesto de mando: Mosquitto (MQTT) + servicios Python (listener USB del gateway ESP32-S3, mensajería, localización GPS, triaje IA con Ollama, dashboard con mapa) + SQLite, orquestado con Docker Compose. Ver [server/README.md](server/README.md). |
| [`firmware/`](firmware/) | Firmware PlatformIO para **ESP32-S3 (gateway)** y **ESP32 (nodo de albergue)** con RFM69HCW + RadioHead RHMesh: trama FSK, AES-128, portal Wi‑Fi cautivo, API para la app y medición de energía solar. Incluye un nodo simulado para probar sin hardware. Ver [firmware/README.md](firmware/README.md). |
| [`config/`](config/) | Configuración de referencia de la red FSK (parámetros de radio, trama, protocolo USB y conexiones SPI). La clave AES real no se sube al repositorio. |
| [`IA_Local_in_Server.md`](IA_Local_in_Server.md) | Arquitectura y especificación técnica del triaje con IA local en el edge (Ollama, Qwen 2.5 1.5B, taxonomía EDAN y piso de seguridad). |

## Descargar la app

- **Con internet:** https://guariosmaster.github.io/Hakaton-UNAL-Sarabhel/ — el APK se compila automáticamente con GitHub Actions en cada cambio de `app/` y queda en la release [`apk-latest`](https://github.com/GuariosMaster/Hakaton-UNAL-Sarabhel/releases/tag/apk-latest).
- **Sin internet, en el puesto de mando:** conectarse al Wi‑Fi del portátil y abrir `http://192.168.137.1:8080/descargar` (copiar antes el APK a `server/descargas/`).

## Usuarios y roles

Inicio de sesión con **usuario único + PIN de 4 dígitos** y tres roles: **administrador**, **puesto de
mando** y **socorrista**. Cada persona **crea su cuenta desde la app** (queda como socorrista; el
administrador da los demás roles). Pedir ayuda (SOS) nunca exige cuenta. Primer uso del sistema: usuario
`admin`, PIN `1234` (se pide cambiarlo). Detalles en [USUARIOS.md](USUARIOS.md).

## Demo para la presentación

`.\iniciar.ps1 -Radio escenario` reproduce un sismo guionizado (mensajes, SOS largo, zona de riesgo,
batería baja) que siempre se desarrolla igual. Guion con lo que hay que decir en cada momento: [DEMO.md](DEMO.md).

## Probar la app entre teléfonos

Sin hardware RF hay dos formas, ambas en [PRUEBAS.md](PRUEBAS.md):

- **Nodo de albergue simulado** (`firmware/herramientas/nodo_simulado.py`): la app se conecta como si fuera al Wi‑Fi de un ESP32 real (conexión **📡 Wi‑Fi del albergue**) y el portal cautivo se puede abrir en el navegador.
- **Puesto de mando**: el servidor del portátil reparte los mensajes entre los teléfonos conectados a su Wi‑Fi (conexión **🖥️ Puesto de mando**).

## Probar sin hardware RF

El listener incluye un modo simulado que emula nodos FSK 915 MHz en Manizales:

```bash
cd server
docker compose up -d --build
# abrir http://localhost:8080
```

## Estado del proyecto

> **Nota (noviembre 2026):** el servidor, la app y el portal están funcionando y probados en **modo simulado** (nodos FSK simulados y nodo de albergue simulado). El firmware ESP32 compila, pero aún no tenemos el dispositivo físico (nodos ESP32 + RFM69HCW y gateway ESP32-S3), por lo que nada se ha probado todavía con radio real FSK.

### Lo que ya está hecho

- [x] **Arquitectura liviana**: Docker Compose + Mosquitto (MQTT) + servicios Python + SQLite, en lugar de Kubernetes, para ahorrar RAM, CPU y batería en el puesto de mando.
- [x] **Listener USB** que lee JSON del gateway ESP32-S3 + RFM69HCW por puerto serie nativo (CDC) a 115.200 baudios, con **modo simulado** de nodos ficticios en Manizales para demos sin hardware.
- [x] **Servicio de mensajería**: guarda el historial y clasifica cada mensaje como crítico, moderado o informativo por palabras clave (SOS, herido, agua…).
- [x] **Triaje inteligente con IA local en el Edge (Ollama + Qwen 2.5 1.5B)**: clasificación 100% offline según la taxonomía **EDAN** (12 categorías: Búsqueda y Rescate `RES`, Salud `SAL`, Albergues `ALB`, etc.), extracción estructurada de necesidades requeridas y generación de resúmenes operativos, con fallback heurístico y piso de seguridad que nunca degrada una alerta crítica previa.
- [x] **Visualización EDAN en Web Dashboard y App Móvil**: badges visuales por categoría con iconos, chips de necesidades extraídas y sincronización en caliente mediante Server-Sent Events (SSE).
- [x] **Servicio de localización GPS**: última posición e historial de cada nodo, batería, y alerta cuando un nodo entra en una zona de riesgo (geocercas).
- [x] **Telemetría de energía**: voltaje de batería, voltaje del panel y % de carga de cada nodo (vienen en cada trama), panel **Energía** en el dashboard y en la app, y alerta de **batería baja**.
- [x] **Dashboard web** del puesto de mando: mapa en vivo, alertas, energía, lista de nodos, recorrido de cada nodo y envío de mensajes a la red.
- [x] **Gestión de alertas**: cada alerta (SOS, zona de riesgo, batería baja) se guarda y se puede marcar como *en atención* / *atendida*, asignar un equipo de rescate y agregar notas, desde el dashboard o la app; los cambios se ven en vivo en todos los equipos.
- [x] **Mensajes de hasta 120 caracteres**: el firmware parte los mensajes largos en tramas `MSGP` y los reensambla al llegar.
- [x] **Kit de energía dimensionado** ([ENERGIA.md](ENERGIA.md)) y **autonomía estimada sin sol** de cada nodo en el dashboard y la app.
- [x] **Escenario de demo guionizado** y guion de presentación ([DEMO.md](DEMO.md)).
- [x] **Exportar CSV** de mensajes y alertas para entregar a las autoridades.
- [x] **APK con firma fija**: las actualizaciones se instalan encima, sin desinstalar.
- [x] **Inicio de sesión con PIN de 4 dígitos y roles** (administrador, puesto de mando, socorrista) en app y dashboard; bloqueo tras 5 intentos; entrada sin conexión para socorristas; botón de emergencia sin cuenta ([USUARIOS.md](USUARIOS.md)).
- [x] **Mejoras de experiencia en la app**: teclado PIN grande, bandeja de salida (lo escrito sin conexión se envía solo al reconectar), reconexión automática, GPS listo al abrir, aviso sonoro y vibración con alertas nuevas, pestaña *Asignadas* para socorristas.
- [x] **Varios gateways**: tablas `gateways` y `enlaces`, alerta si un gateway se desconecta, duplicados descartados, respuesta por el gateway con mejor señal y la red dibujada en el mapa del dashboard.
- [x] **Firmware ESP32** (PlatformIO): gateway ESP32-S3 (USB JSON ↔ radio) y nodo de albergue (portal Wi‑Fi cautivo, API para la app, medición de batería/panel, telemetría cada 5 min, malla RHMesh, AES-128). Compila; falta probarlo en hardware.
- [x] **Nodo de albergue simulado** en Python con la misma API y portal que el firmware, para probar la app y el portal sin hardware.
- [x] Configuración de referencia de la red FSK (sin claves expuestas).
- [x] Pruebas unitarias (prioridad, paquetes, geocercas).
- [x] **App móvil Android** (React + Capacitor) con modo Campo (conexión al Wi‑Fi del nodo de albergue, SOS con GPS del teléfono, mensajes rápidos, chat, mapa) y modo Puesto de mando (alertas, mapa, mensajes, energía). Probada en el navegador con el nodo simulado y con el servidor.

### Lo que falta

**Necesita el dispositivo físico**
- [ ] Probar el listener USB con el gateway ESP32-S3 + RFM69HCW real.
- [ ] Probar la app móvil por el portal Wi-Fi local del nodo con hardware real e instalar el APK en varios teléfonos.
- [ ] Cargar el firmware en las placas y verificar radio, portal y medición de energía (calibrar divisores resistivos).
- [ ] Pruebas de enlace RF en Manizales (distancia, RSSI, tasa de entrega, consumo energético).
- [ ] Probar el despliegue con Docker en el servidor Ubuntu del PMU.

**Se puede avanzar sin hardware**
- [ ] **Medir el consumo real** de los nodos y ajustar el dimensionamiento de [ENERGIA.md](ENERGIA.md).
- [ ] **Buzón** para nodos desconectados (reintentar mensajes cuando el nodo vuelva a tener ruta).
- [ ] **Mapa offline** de Manizales (mosaicos servidos en local; hoy el mapa usa internet).
- [ ] **Zonas de riesgo oficiales** (POT / Corpocaldas); las actuales son polígonos de ejemplo.
- [ ] Estadísticas en el dashboard (mensajes por prioridad, tiempos de atención).

**Documentación**
- [ ] Unificar las propuestas técnicas en un solo documento alineado con lo construido (el borrador `add_fsk_v1.md` aún no está en el repositorio).
- [ ] Definir hardware: placas ESP32-S3, ESP32 DevKit V1, ESP32-C6, transceptores RFM69HCW 915 MHz, paneles solares y baterías LiFePO4.
