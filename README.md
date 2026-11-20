# Lora-Hakaton

Cuando cae la red celular, la coordinación se cae con ella. Este prototipo propone lo contrario: una red que se arma entre los propios nodos, sigue funcionando sin internet y permite ver dónde está cada uno.

La capa de radio no se construye desde cero: usamos **Meshtastic**, un proyecto open source de malla LoRa, para el descubrimiento, el reenvío de mensajes y la cobertura sin torres ni SIM. La innovación está en lo que construimos encima:

- un **mapa con localización GPS** de los nodos activos, para entender la cobertura de la red;
- un **servidor local de analítica** que recibe, organiza y consulta los mensajes de la malla;
- el dimensionamiento de un **kit de energía** (panel solar y/o eólico, en evaluación) para sostener la operación cuando falte el suministro eléctrico.

El resultado buscado no es solo que los nodos se hablen: es que esa información llegue a quien decide en el territorio, incluso cuando no hay señal.

## Estructura del repositorio

| Carpeta | Contenido |
|---|---|
| [`server/`](server/) | Servidor local del puesto de mando: Mosquitto (MQTT) + servicios Python (listener, mensajería, localización GPS, dashboard con mapa) + SQLite, orquestado con Docker Compose. Ver [server/README.md](server/README.md). |
| [`config/`](config/) | Configuración de referencia de los nodos Meshtastic (sin claves). |

## Probar sin hardware

El listener tiene un modo simulado con 5 nodos ficticios en Manizales:

```bash
cd server
docker compose up -d --build
# abrir http://localhost:8080
```

## Estado del proyecto

> **Nota (noviembre 2026):** el software del servidor está funcionando y probado en
> **modo simulado**. Aún no tenemos el dispositivo físico (nodos y gateway LoRa), por lo
> que nada se ha probado todavía con radio real.

### Lo que ya está hecho

- [x] **Arquitectura liviana**: Docker Compose + Mosquitto (MQTT) + servicios Python + SQLite,
      en lugar de Kubernetes, para ahorrar RAM, CPU y batería en el puesto de mando.
- [x] **Listener** que se conecta al gateway Meshtastic por USB/serie o Wi‑Fi (TCP), con un
      **modo simulado** de 5 nodos ficticios en Manizales para demos sin hardware.
- [x] **Servicio de mensajería**: guarda el historial y clasifica cada mensaje como
      crítico, moderado o informativo por palabras clave (SOS, herido, agua…).
- [x] **Servicio de localización GPS**: última posición e historial de cada nodo, batería,
      y alerta cuando un nodo entra en una zona de riesgo (geocercas).
- [x] **Dashboard web** del puesto de mando: mapa en vivo, alertas, lista de nodos,
      recorrido de cada nodo y envío de mensajes a la red.
- [x] Configuración de referencia de los nodos sin claves y con el MQTT público apagado.
- [x] Pruebas unitarias (prioridad, paquetes, geocercas).

### Lo que falta

**Necesita el dispositivo físico**
- [ ] Probar el listener con el gateway Meshtastic real (USB y Wi‑Fi).
- [ ] Aplicar `config/meshtastic.example.yaml` a los nodos.
- [ ] Pruebas de alcance en Manizales (distancia, RSSI/SNR) y medición del consumo real de cada nodo.
- [ ] Probar el despliegue con Docker en el servidor Ubuntu.

**Se puede avanzar sin hardware**
- [ ] **Gestión de alertas**: marcar una alerta como atendida, asignar equipo de rescate y agregar notas.
- [ ] **Kit de energía**: dimensionar panel, batería y autonomía (nodos y servidor) y mostrarlo en el dashboard.
- [ ] **Escenario de demo guionizado** (un "sismo" simulado que siempre se desarrolla igual).
- [ ] **Confirmación de entrega y buzón** para nodos desconectados.
- [ ] **Mapa offline** de Manizales (mosaicos servidos en local; hoy el mapa usa internet).
- [ ] **Zonas de riesgo oficiales** (POT / Corpocaldas); las actuales son polígonos de ejemplo.
- [ ] Estadísticas y exportación de reportes (CSV).
- [ ] Contraseña de acceso al dashboard.

**Documentación y compras**
- [ ] Unificar las propuestas técnicas en un solo documento alineado con lo construido.
- [ ] Definir y comprar hardware: placas con GPS (p. ej. LilyGO T‑Beam o Heltec Wireless Tracker),
      antenas de 915 MHz, panel solar y baterías 18650.
