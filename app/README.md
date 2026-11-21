# App móvil — Red de Emergencia FSK 915 MHz

App Android propia del proyecto. Funciona **sin internet ni señal celular**. Tiene dos modos:

| Modo | Para quién | Cómo se conecta | Qué hace |
|---|---|---|---|
| **Campo** | Brigadistas y comunidad | **Wi‑Fi del nodo de albergue** (ESP32 + RFM69HCW) | Botón **SOS** (mantener presionado), mensajes rápidos, chat, mapa y energía de los nodos. Cada SOS va con la **ubicación GPS del teléfono**. |
| **Puesto de mando** | Coordinadores | **Wi‑Fi local** del puesto de mando, hacia el servidor (`server/`) | Alertas en vivo (SOS, zona de riesgo, batería baja), mapa con zonas de riesgo, mensajes hacia cualquier albergue y panel de **energía**. |

```
Campo:  [App] ─Wi‑Fi "Emergencia …"─► [Nodo de albergue] ~~~ radio FSK 915 MHz (RHMesh) ~~~► [Gateway ESP32-S3] ─USB─► [Servidor]
Mando:  [App] ─Wi‑Fi local del puesto de mando───────────────────────────────────────────────────────────► [Servidor]
```

En modo Campo hay tres formas de conectarse:

- **📡 Wi‑Fi del albergue**: a la red que crea el nodo ESP32 (`http://192.168.4.1`). Es el uso real
  en campo. Quien no tenga la app puede usar el portal que se abre solo al conectarse a esa red.
- **🖥️ Puesto de mando**: por Wi‑Fi al servidor, que reparte los mensajes entre teléfonos y los
  envía por radio a los albergues. Sirve para quien está en el puesto y para probar entre teléfonos.
- **🧪 Demo**: todo simulado dentro del teléfono.

Para probar sin hardware: [PRUEBAS.md](../PRUEBAS.md) (incluye un nodo de albergue simulado).

## Tecnología

- **React + TypeScript + Vite**: la interfaz.
- **Capacitor 8**: empaqueta la app web como app Android nativa (GPS nativo con `@capacitor/geolocation`).
- **Leaflet**: mapa. Viene incluido en la app, no se descarga de internet.
- Sin dependencias de radio en el teléfono: la app habla HTTP con el nodo; la radio la maneja el ESP32.

## Estructura

```
src/
  lib/mesh/albergue.ts   conexión al nodo ESP32 por su Wi‑Fi (API del firmware)
  lib/mesh/lan.ts        conexión al servidor del puesto de mando
  lib/mesh/sim.ts        modo demo
  lib/server.ts          cliente del servidor (REST + eventos en vivo)
  lib/priority.ts        clasificación crítico/moderado/informativo (igual que el servidor)
  store/                 estado de cada modo (zustand)
  screens/               pantallas de Campo y de Mando
android/                 proyecto Android generado por Capacitor
```

## Límite de texto

Cada mensaje admite **120 bytes**. Hasta 36 viaja en un solo paquete de radio; más largo, el nodo lo
parte en varios paquetes. La ubicación del SOS no gasta texto: viaja en una trama POS aparte.

## Firma del APK

Todos los APK (locales y de GitHub Actions) se firman con la clave de pruebas
`android/app/keystore/pruebas.keystore`, así que **las actualizaciones se instalan encima** sin
desinstalar. Esa clave es pública (está en el repositorio): para publicar en Google Play hay que crear
una clave privada aparte.

> Si compilas dentro de una carpeta de OneDrive y Gradle falla con *"not a regular file"* o *"Unable to
> delete directory"*, es OneDrive bloqueando archivos recién copiados: borra
> `android/app/src/main/assets/public`, ejecuta `npx cap copy android` y compila de nuevo.

## Desarrollo

```powershell
npm install
npm run dev          # abre http://localhost:5173 (usar vista de celular en el navegador)
```

## Generar el APK de Android

Requiere Android Studio (incluye el JDK 21 y el SDK de Android). GitHub Actions lo compila solo en
cada cambio de `app/` y lo publica en la página de descarga.

```powershell
npm run build
npx cap sync android
cd android
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
.\gradlew assembleDebug
```

El APK queda en `android/app/build/outputs/apk/debug/app-debug.apk`.

## Nota sobre Android y redes sin internet

Cuando el teléfono se conecta al Wi‑Fi del nodo (que no tiene internet), Android puede avisar
“sin internet” y seguir usando los datos móviles. Hay que elegir **mantener conexión** o apagar los
datos móviles mientras se usa la red de emergencia.

## Pendiente (necesita el hardware)

- Probar la conexión con un nodo ESP32 real e instalar el APK en varios teléfonos.
- Mapa offline en el teléfono.
