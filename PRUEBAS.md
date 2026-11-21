# Cómo probar sin el hardware FSK

Mientras no tengamos los ESP32 + RFM69HCW, se puede probar todo el recorrido con piezas simuladas
que hablan exactamente igual que las reales.

```
[Teléfono] ─Wi‑Fi─► [Nodo de albergue SIMULADO] ─"radio" (MQTT)─► [Servidor] ─► Dashboard / app Mando
[Teléfono] ─Wi‑Fi─────────────────────────────────────────────► [Servidor]   (conexión "Puesto de mando")
```

## Qué se necesita

- El portátil con el proyecto (Windows).
- Uno o más teléfonos Android con la app ([descarga](https://guariosmaster.github.io/Hakaton-UNAL-Sarabhel/)),
  en la **misma red Wi‑Fi** que el portátil: la de la casa, el hotspot del teléfono o la zona con
  cobertura del portátil. No hace falta internet. (Las redes de la universidad suelen aislar a los
  dispositivos entre sí: mejor usar un hotspot.)

## 1. Iniciar el servidor

Desde la carpeta `server`:

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar.ps1
```

Se abren varias ventanas (no cerrarlas). Al final aparece la dirección para los teléfonos, por
ejemplo `http://10.165.0.184:8080`. Con `-Radio ninguno` no se simulan nodos FSK de fondo.

> Si los teléfonos no conectan, permite a Python en el Firewall de Windows o abre el puerto 8080
> (PowerShell como administrador):
> `New-NetFirewallRule -DisplayName "Red Emergencia (pruebas)" -Direction Inbound -Protocol TCP -LocalPort 8080,8765 -Action Allow -Profile Private,Public`

## 2. Iniciar un nodo de albergue simulado

En otra ventana, desde la raíz del proyecto:

```powershell
server\.venv\Scripts\python firmware\herramientas\nodo_simulado.py --nodo 7 --nombre "Albergue Bosques"
```

Queda en `http://<ip-del-pc>:8765` con la **misma API y el mismo portal** que el firmware del ESP32.

## 3. Probar

**Portal (sin app):** abre `http://<ip-del-pc>:8765` en el navegador del teléfono. Es la página que
verá cualquier persona al conectarse al Wi‑Fi “Emergencia …” de un nodo real.

**App, modo Campo → 📡 Wi‑Fi del albergue:** en “Dirección del nodo” escribe `http://<ip-del-pc>:8765`
→ Conectar al nodo. (Con el nodo real se deja la dirección por defecto, `http://192.168.4.1`.)
Prueba el SOS y los mensajes rápidos: llegan al servidor con la ubicación GPS del teléfono.

**App, modo Campo → 🖥️ Puesto de mando:** tu nombre y `http://<ip-del-pc>:8080`. Sirve para probar
mensajes entre varios teléfonos.

**Puesto de mando:** en el portátil abre `http://localhost:8080`, o en otro teléfono la app en modo
**Puesto de mando**. Desde ahí se ven alertas, mapa y la **energía** de cada nodo, y se pueden enviar
mensajes a un albergue (aparecen en su portal y en la app conectada a él).

## Qué se está probando y qué no

| Se prueba | No se prueba todavía |
|---|---|
| App, portal, API del nodo y servidor de punta a punta | El enlace de radio FSK real y su alcance |
| SOS con GPS (trama POS + MSG), mensajes rápidos, chat | El firmware corriendo en las placas |
| Clasificación de prioridad, alertas, energía y batería baja | La medición real de batería y panel (divisores) |
| Mensajes del puesto de mando hacia un albergue | El consumo de energía de los nodos |

## Cuando llegue el hardware

1. Cargar el firmware ([firmware/README.md](firmware/README.md)).
2. Conectar el gateway ESP32-S3 por USB y arrancar `.\iniciar.ps1 -Radio usb`.
3. En el teléfono, conectarse al Wi‑Fi **“Emergencia &lt;albergue&gt;”** del nodo y usar la app con
   **📡 Wi‑Fi del albergue** (dirección `http://192.168.4.1`), o simplemente el portal que se abre solo.
