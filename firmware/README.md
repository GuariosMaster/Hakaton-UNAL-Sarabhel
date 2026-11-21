# Firmware ESP32 — red FSK 915 MHz

Dos programas sobre **ESP32 + RFM69HCW** con **RadioHead RHMesh**:

| Programa | Placa | Qué hace |
|---|---|---|
| [`src/gateway`](src/gateway/main.cpp) | ESP32-S3 (dirección 1) | Puente entre la radio y el servidor: cada trama recibida sale por USB como una línea JSON; las líneas JSON que llegan del servidor se transmiten por radio. Reporta la energía del kit del puesto de mando. |
| [`src/nodo`](src/nodo/main.cpp) | ESP32 DevKit V1 (o S3 / C6) | Nodo de albergue: crea la red Wi‑Fi abierta **“Emergencia &lt;nombre&gt;”** con **portal cautivo**, una API para la app móvil, mide batería y panel solar, envía reportes y telemetría por radio y reenvía tramas de otros nodos (malla). |

Parámetros de radio, trama y conexiones: [`config/README.md`](../config/README.md).

## Compilar y cargar

Requiere [PlatformIO](https://platformio.org/) (extensión de VS Code o `pip install platformio`).

```bash
cd firmware
cp include/clave.example.h include/clave.h     # y cambiar los 16 bytes de la clave AES
pio run -e gateway_esp32s3 -t upload             # gateway (conectar el ESP32-S3 por USB)
pio run -e nodo_esp32 -t upload                  # nodo de albergue
pio device monitor                               # ver lo que imprime la placa
```

Cada nodo necesita una **dirección distinta (2–254)** y un nombre: en `platformio.ini` cambiar
`-DNODE_ADDRESS` y `-DNODE_NAME`, o copiar el entorno `nodo_esp32_3` como plantilla.

## Portal Wi‑Fi del nodo

Al conectarse a la red “Emergencia …”, Android/iOS muestran la página automáticamente (portal
cautivo). Desde ahí cualquier persona envía un SOS o un reporte corto sin instalar nada. La app
móvil usa la misma red con la API:

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/estado` | `{"nodo","nombre","bat","panel","carga","conectados","max_texto"}` |
| GET | `/api/mensajes?desde=N` | Mensajes recibidos por radio desde el número de secuencia N |
| POST | `/api/mensaje` | `{"msg","dest","lat","lon"}` → trama POS (si hay ubicación) + trama MSG |
| POST | `/api/posicion` | `{"lat","lon"}` → trama POS |

## Probar sin hardware

[`herramientas/nodo_simulado.py`](herramientas/nodo_simulado.py) imita un nodo en el PC con la
misma API y el mismo portal. Si el servidor está corriendo, sus mensajes llegan al dashboard como
si viajaran por radio, y lo que el puesto de mando le envía aparece en el portal:

```powershell
server\.venv\Scripts\python firmware\herramientas\nodo_simulado.py --nodo 7 --nombre "Albergue Bosques"
# portal en http://localhost:8765 — en la app: Wi‑Fi del albergue → http://<ip-del-pc>:8765
```

## Límites conocidos

- **Texto de 36 bytes por mensaje**: un paquete RHMesh sobre RFM69 lleva 54 bytes y la trama
  ocupa 18. Para mensajes más largos habría que fragmentar.
- **RHMesh no reenvía difusiones**: para “todos”, el gateway envía el mensaje a cada nodo que conoce.
- **Alcance**: FSK a 9,6 kbps tiene menos sensibilidad que LoRa; prever repetidores en las laderas y
  medir el alcance real con el hardware.
- **ESP32-C6**: necesita Arduino-ESP32 3.x (plataforma pioarduino, ver comentario en `platformio.ini`).
- La red Wi‑Fi del nodo es **abierta** a propósito (emergencia); el enlace de radio sí va cifrado con AES-128.
