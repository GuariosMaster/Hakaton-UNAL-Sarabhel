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

## Estado

- [x] Servidor local con mensajería, prioridad de alertas y localización GPS (probado en modo simulado)
- [ ] Prueba con gateway Meshtastic real
- [ ] Mapa offline de Manizales y zonas de riesgo oficiales
- [ ] Dimensionamiento del kit de energía
