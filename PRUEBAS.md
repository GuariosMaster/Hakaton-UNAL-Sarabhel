# Cómo probar la app entre teléfonos (sin nodos LoRa)

Mientras no tengamos el dispositivo físico, el **servidor administrador** (el portátil del
puesto de mando) hace de red: reparte los mensajes entre los teléfonos conectados a su Wi‑Fi.

```
[Teléfono A] ─┐                                    ┌─ Dashboard web (http://localhost:8080)
              ├─ Wi‑Fi ─► [Servidor en el portátil] ┤
[Teléfono B] ─┘                                    └─ App en modo Puesto de mando
```

## Qué se necesita

- El portátil con el proyecto (Windows).
- Dos o más teléfonos Android con la app instalada
  (descargarla en https://guariosmaster.github.io/Lora-Hakaton/).
- Que el portátil y los teléfonos estén en **la misma red Wi‑Fi**. Sirve:
  - el Wi‑Fi de la casa o de la universidad, o
  - la **zona con cobertura** del portátil (Configuración → Red e Internet → Zona con cobertura
    inalámbrica móvil). No necesita internet.

## Paso a paso

1. **Iniciar el servidor** en el portátil, desde la carpeta `server`:

   ```powershell
   .\iniciar.ps1 -Radio ninguno
   ```

   Se abren varias ventanas (no cerrarlas) y al final aparece la dirección para los teléfonos,
   por ejemplo `http://192.168.1.20:8080`. Con `-Radio sim` se agregan además 5 nodos LoRa simulados.

   > La primera vez Windows puede preguntar si permite a Python en la red: elegir **Permitir**
   > en **redes privadas**. Si no aparece y los teléfonos no conectan, revisar el Firewall de Windows.
   >
   > Si PowerShell no deja ejecutar el script: `powershell -ExecutionPolicy Bypass -File .\iniciar.ps1 -Radio ninguno`

2. **Teléfono A**: abrir la app → **Estoy en campo** → pestaña **Conexión** → **📶 Red local**.
   Escribir un nombre (por ejemplo "Brigada Ana") y la dirección del servidor → **Conectar por Wi‑Fi**.

3. **Teléfono B**: lo mismo, con otro nombre (por ejemplo "Rescate Luis").

4. **Probar**:
   - En **Mensajes**, enviar a "Todos" o elegir el otro teléfono como destinatario.
   - En **SOS**, mantener presionado el botón o usar un mensaje rápido: llega con la ubicación GPS.
   - En el **Mapa** aparece la ubicación de cada teléfono que haya enviado un SOS.

5. **Ver el puesto de mando**:
   - En el portátil: abrir `http://localhost:8080` (dashboard web con mapa y alertas), o
   - en un tercer teléfono: app → **Puesto de mando** → dirección del servidor.
   Desde ahí también se pueden enviar mensajes a los teléfonos.

## Qué se está probando y qué no

| Se prueba | No se prueba todavía |
|---|---|
| Interfaz de la app, envío y recepción de mensajes entre teléfonos | El alcance por radio LoRa |
| SOS con GPS del teléfono y mensajes rápidos | La conexión Bluetooth con un nodo real |
| Clasificación de prioridad y alertas en el puesto de mando | El consumo de energía de los nodos |
| Mapa, mensajes directos y respuesta del puesto de mando | |

Cuando lleguen los nodos, se cambia **Red local** por **🔵 Bluetooth** en la app y el servidor
se inicia con `.\iniciar.ps1 -Radio serial -Puerto COM5` (el puerto del gateway).
