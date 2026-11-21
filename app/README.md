# App móvil — Red de Emergencia LoRa

App Android propia del proyecto. Funciona **sin internet ni señal celular**. Tiene dos modos:

| Modo | Para quién | Cómo se conecta | Qué hace |
|---|---|---|---|
| **Campo** | Brigadistas y comunidad | **Bluetooth** al nodo LoRa que lleva la persona | Botón **SOS** (mantener presionado), mensajes rápidos, chat con la red, mapa de nodos. Cada SOS va con la **ubicación GPS del teléfono**. |
| **Puesto de mando** | Coordinadores | **Wi‑Fi local** del puesto de mando, hacia el servidor (`server/`) | Alertas en vivo, mapa de toda la red con zonas de riesgo y mensajes hacia cualquier nodo. |

```
Campo:  [App] ─Bluetooth─► [Nodo LoRa] ~~~ malla LoRa ~~~► [Gateway] ─USB─► [Servidor]
Mando:  [App] ─Wi‑Fi local (hotspot del portátil)───────────────────────────► [Servidor]
```

En modo Campo hay tres formas de conectarse:

- **🔵 Bluetooth**: al nodo LoRa propio (uso real en campo).
- **📶 Red local**: por Wi‑Fi al servidor del puesto de mando, que reparte los mensajes entre
  teléfonos. Sirve para probar entre varios teléfonos sin nodos ([PRUEBAS.md](../PRUEBAS.md)) y
  para teléfonos cerca del puesto de mando.
- **🧪 Modo demo**: todo simulado dentro del teléfono.

Los dos modos tienen **modo demo** (radio simulada en Campo, servidor en modo `sim` en Mando),
así que la app se puede presentar sin el dispositivo físico.

## Tecnología

- **React + TypeScript + Vite**: la interfaz.
- **Capacitor 8**: empaqueta la app web como app Android nativa.
- **@capacitor-community/bluetooth-le**: Bluetooth LE nativo (en Chrome de escritorio usa Web Bluetooth).
- **@meshtastic/protobufs**: protocolo oficial de Meshtastic. El cliente del protocolo está en
  [`src/lib/mesh/protocol.ts`](src/lib/mesh/protocol.ts) y es nuestro.
- **Leaflet**: mapa. Viene incluido en la app, no se descarga de internet.

## Estructura

```
src/
  lib/mesh/      protocolo Meshtastic, transporte Bluetooth y radio simulada
  lib/server.ts  cliente del servidor del puesto de mando (REST + eventos en vivo)
  lib/priority.ts  clasificación crítico/moderado/informativo (igual que el servidor)
  store/         estado de cada modo (zustand)
  screens/       pantallas de Campo y de Mando
android/         proyecto Android generado por Capacitor
```

## Desarrollo

```powershell
npm install
npm run dev          # abre http://localhost:5173 (usar vista de celular en el navegador)
```

En el navegador, el modo Campo funciona con **Modo demo**. Con un nodo real se puede probar
desde **Chrome de escritorio** (Web Bluetooth) con el botón **Bluetooth**.

Para el modo Mando en el PC: levantar el servidor (`server/`) y usar `http://localhost:8080`.

## Generar el APK de Android

Requiere Android Studio (incluye el JDK 21 y el SDK de Android).

```powershell
npm run build
npx cap sync android
cd android
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
.\gradlew assembleDebug
```

El APK queda en `android/app/build/outputs/apk/debug/app-debug.apk`. Para instalarlo, copiarlo
al teléfono y abrirlo (activar "Instalar apps de origen desconocido"), o usar
`npx cap run android` con el teléfono conectado por USB y la depuración USB activada.

También se puede abrir el proyecto en Android Studio con `npx cap open android`.

## Uso en el puesto de mando

1. En el portátil del servidor: **Configuración → Red e Internet → Zona con cobertura
   inalámbrica móvil** y activarla. Funciona sin internet.
2. Conectar los teléfonos de los coordinadores a esa red Wi‑Fi.
3. En la app, modo **Puesto de mando**, dirección `http://192.168.137.1:8080` (es la IP que usa
   Windows para el portátil en la zona con cobertura).

## Pendiente (necesita el dispositivo físico)

- Probar el Bluetooth con un nodo Meshtastic real: emparejamiento, envío y recepción.
  El código sigue el protocolo oficial, pero **todavía no se ha probado con hardware**.
- Confirmar el tamaño de paquete (MTU) en distintos teléfonos Android.
- Confirmación de entrega a destinatario específico (hoy se muestra "recibido por la red").
- Mapa offline para el modo Campo (descargar mosaicos de Manizales al teléfono).
