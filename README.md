# Sarabhel — Sistema C4I Táctico de Emergencia (FSK 915 MHz + IA Edge)

> **Plataforma autónoma de comunicaciones críticas, telemetría y triaje asistido por IA local (Edge Computing) para Puestos de Mando Unificado (PMU) y zonas de desastre sin conectividad eléctrica, celular ni internet.**

---

## 1. Visión general del sistema

Cuando ocurre un desastre natural (terremoto, deslizamiento, erupción volcánica), las redes comerciales de telecomunicaciones y el fluido eléctrico colapsan en minutos. **Sarabhel** restablece la visibilidad operativa y la línea de mando conectando albergues, brigadistas en campo y el Puesto de Mando Unificado (PMU) mediante una red física resiliente y análisis táctico automatizado.

```
[ Celulares en Albergue ]
         │ (Wi-Fi local 192.168.4.1)
         ▼
┌─────────────────────────┐
│ Nodo Albergue (ESP32)   │ ◄── Batería LiFePO4 + Panel Solar
└───────────┬─────────────┘
            │
            ▼ (Radio Malla FSK 915 MHz — AES-128 — RadioHead RHMesh)
┌─────────────────────────┐
│ Gateway PMU (ESP32-S3)  │
└───────────┬─────────────┘
            │ (USB Serie / CDC a 115200 baudios)
            ▼
┌───────────────────────────────────────────────────────────────┐
│  Puesto de Mando Unificado (PMU) — Servidor Local Docker      │
│  ├── Mosquitto (Broker MQTT interno)                         │
│  ├── Microservicios Python (Listener, Mensajería, GPS)        │
│  ├── Motor de Triaje IA Local: Ollama (Qwen 2.5 1.5B)         │
│  └── Dashboard Web + App Móvil (Leaflet, Mapas, Alertas)      │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. Arquitectura en 4 capas

| Capa | Componente | Descripción técnica |
|---|---|---|
| **1. Radio Malla Sub-GHz** | Hardware RFM69HCW + ESP32 | Banda ISM 915.0 MHz FSK (+20 dBm), cifrado hardware AES-128, enrutamiento en malla dinámico con **RadioHead RHMesh**. Telemetría de energía solar y batería en cada trama. |
| **2. Servidor PMU Local** | Docker Compose + Python + MQTT | Orquestación liviana en host local. Broker **Mosquitto MQTT (QoS 1)**, listener serie USB, ingesta de mensajes, motor geográfico de geocercas y base de datos persistente SQLite (modo WAL). |
| **3. Triaje con IA Local** | Edge LLM: Ollama + Qwen 2.5 1.5B | Inferencia 100% offline (~986 MB RAM). Clasificación bajo taxonomía estándar **EDAN** (12 categorías de desastre), extracción de requerimientos operativos y piso de seguridad determinista. |
| **4. Interfaces Tácticas** | Web Dashboard + App Android | Dashboard web reactivo en tiempo real (Leaflet, SSE) y App Android nativa (React + Capacitor) con modos **Campo** (portal Wi-Fi directo del nodo) y **Puesto de Mando**. |

---

## 3. Motor de Triaje con IA Local (Edge Computing)

El PMU no depende de conexiones satelitales ni de APIs en la nube (como OpenAI o Claude) para procesar el flujo de emergencias. El servidor integra un modelo de lenguaje de última generación optimizado para el borde:

- **Modelo**: `qwen2.5:1.5b` vía **Ollama**, ejecutándose localmente en CPU o GPU ligera.
- **Taxonomía EDAN (12 ramas estándar)**:
  - `RES`: Búsqueda y Rescate (atrapados, estructuras colapsadas)
  - `SAL`: Salud y Atención Médica (heridos, triage, medicamentos)
  - `ALB`: Albergues Temporales y Evacuación
  - `AGU`: Agua Potable y Saneamiento
  - `ALI`: Alimentos y Nutrición
  - `SEG`: Seguridad y Orden Público
  - `DAN`: Evaluación de Daños en Infraestructura
  - `LOG`: Logística, Transporte y Combustible
  - `AMB`: Afectación Ambiental y Materiales Peligrosos
  - `COM`: Telecomunicaciones
  - `ENE`: Energía y Servicios Básicos
  - `INF`: Informativo general / Sin afectación
- **Extracción de Requerimientos**: El modelo identifica automáticamente qué recursos solicita el reporte (ej. *ambulancia medicalizada*, *camillas*, *kit de sutura*, *planta eléctrica*).
- **Piso de Seguridad Inmutable**: Si un mensaje contiene palabras de riesgo vital inminente (`SOS`, `atrapado`, `muriendo`), el sistema asigna prioridad crítica de forma determinista y el LLM **nunca** puede degradar esa severidad.

Detalles de arquitectura en [IA_Local_in_Server.md](IA_Local_in_Server.md).

---

## 4. Semántica visual del mapa y nodos

Tanto en el **Dashboard Web** del PMU como en la **App Móvil**, el mapa táctico refleja la criticidad de la situación mediante dos componentes visuales:

### Colores de los Nodos (Balizas en el mapa)

```
   🔴 CRÍTICO          🟡 MODERADO          🟢 OPERATIVO         ⚪ INACTIVO
[ SOS / Atrapados ]   [ Víveres / Agua ]   [ Patrulla Normal ]   [ Sin baliza >30m ]
[ Geocerca Riesgo ]   [ Batería < 20%  ]
```

- 🔴 **Rojo (Crítico / Alerta Máxima)**: Nodo que ha emitido un mensaje clasificado como crítico por el motor de triaje (SOS, rescate, personas en riesgo vital) o cuya posición GPS se encuentra dentro de un polígono de riesgo activo.
- 🟡 **Amarillo / Naranja (Moderado / Recursos)**: Nodo con requerimientos operacionales estándar (solicitud de alimentos, agua, medicamentos, cobijas) o advertencia de telemetría de energía (batería < 20%).
- 🟢 **Verde (Normal / Operativo)**: Nodo en servicio regular reportando telemetría estable y mensajes informativos.
- ⚪ **Gris (Inactivo / Stale)**: Nodo cuya última baliza o reporte supera los 30 minutos sin comunicación.

### Geocercas de Riesgo Físico (Polígonos Rojos en el Mapa)

Los polígonos delimitados en rojo (por ejemplo, *Cañada Chipre* y *Ladera Aranjuez* en Manizales) representan **amenazas físicas estáticas del terreno** (fallas geológicas, cuencas de torrencialidad, laderas con riesgo de deslizamiento) cargadas desde `zones/zonas_riesgo.geojson`.
- **Detección automática**: El microservicio de localización evalúa continuamente las coordenadas GPS reportadas por cada nodo mediante un algoritmo de *ray-casting*.
- **Activación de Alerta**: En el instante en que un brigadista o nodo ingresa a las coordenadas de la geocerca, el sistema dispara automáticamente una alerta de zona de riesgo en el PMU y tiñe el nodo de rojo.

---

## 5. Contrato de Protocolo: App ↔ Nodo ESP32

El nodo de albergue expone un punto de acceso Wi-Fi local (`192.168.4.1`) con un endpoint unificado para la comunicación sin internet:

**`POST http://192.168.4.1/api/mensaje`**

### Tipo 1: Chat / Mensajería de Emergencia
```json
{
  "tipo": "chat",
  "mensaje": "Albergue Norte requiere 50 kits de aseo y 2 médicos generales",
  "destino": 0,
  "lat": 5.0689,
  "lon": -75.5174
}
```

### Tipo 2: Autenticación / Registro de Socorrista
```json
{
  "tipo": "login",
  "usuario": "carlos_socorrista",
  "pin": "1234",
  "destino": 0
}
```

---

## 6. Estructura del repositorio

| Directorio | Propósito y Contenido |
|---|---|
| [`server/`](server/) | Puesto de Mando: Docker Compose con Mosquitto, Ollama, listener serie, servicios Python (mensajería, GPS, triaje) y Dashboard Web en puerto `8080`. |
| [`app/`](app/) | Aplicación móvil Android (React 19 + Capacitor 8 + Tailwind CSS). Soporta modo Campo (Wi-Fi del nodo) y modo PMU (Wi-Fi del servidor). |
| [`firmware/`](firmware/) | Código C++ PlatformIO para **ESP32-S3 (Gateway USB)** y **ESP32 DevKit V1 (Nodo Albergue)** con RFM69HCW + RadioHead RHMesh. |
| [`web/`](web/) | Portal estático ligero para descarga local del APK en albergues o PMU sin internet (`/descargar`). |
| [`config/`](config/) | Parámetros técnicos de referencia de la modulación FSK 915 MHz, SPI pins y estructura de tramas. |
| [`IA_Local_in_Server.md`](IA_Local_in_Server.md) | Especificación exhaustiva del pipeline de IA local, prompts de triaje EDAN y fallback heurístico. |

---

## 7. Puesta en marcha rápida (Quickstart)

### Opción A: Modo Simulado Completo (Sin Hardware RF)

Permite validar toda la plataforma (Dashboard, Ollama, Malla simulada y App) en un portátil:

1. **Clonar e iniciar el stack de contenedores**:
   ```bash
   cd server
   docker compose up -d --build
   ```
2. **Descargar el modelo en Ollama**:
   ```bash
   docker exec -it ollama ollama pull qwen2.5:1.5b
   ```
3. **Acceder a los servicios**:
   - **Dashboard PMU**: [http://localhost:8080](http://localhost:8080) (Usuario inicial: `admin` / PIN: `1234`)
   - **Nodo Albergue Simulado**: [http://localhost:8765](http://localhost:8765) (Simula el Wi-Fi del ESP32 físico)
   - **Descarga de APK**: [http://localhost:8080/descargar](http://localhost:8080/descargar)

### Opción B: Modo Producción con Hardware Real

1. Conectar el **ESP32-S3 Gateway** con transceptor RFM69HCW por puerto USB al servidor PMU (`/dev/ttyACM0`).
2. Configurar `server/docker-compose.yml` para mapear el dispositivo serial:
   ```yaml
   devices:
     - /dev/ttyACM0:/dev/ttyACM0
   ```
3. Encender los nodos de albergue ESP32 alimentados por batería LiFePO4 / panel solar.
4. Conectar la app móvil al Wi-Fi del nodo (`Sarabhel-Albergue-XX`) en campo o al Wi-Fi del PMU en puesto de mando.

---

## 8. Descarga de la App Móvil

- **Repositorio / GitHub Releases**: [RedEmergencia.apk](https://github.com/GuariosMaster/Hakaton-UNAL-Sarabhel/releases/download/apk-latest/RedEmergencia.apk) (Compilación continua vía GitHub Actions).
- **En el puesto de mando sin internet**: Conectarse al Wi-Fi del servidor y descargar desde `http://<IP_SERVIDOR>:8080/descargar`.

---

## 9. Licencia y Créditos

Desarrollado para el reto de innovación y resiliencia en gestión de desastres — **Hackatón UNAL 2026**. Equipo Sarabhel.
