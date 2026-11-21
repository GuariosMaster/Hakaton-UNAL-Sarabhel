# Kit de energía — dimensionamiento

Cálculo de referencia para que cada nodo de albergue y el puesto de mando funcionen sin red
eléctrica. Los consumos son **valores típicos de hoja de datos**: hay que **medirlos con el
hardware real** (multímetro en serie con la batería) y ajustar este documento y las variables
`NODE_BATTERY_WH` / `NODE_CONSUMPTION_W` del servidor.

## 1. Nodo de albergue (ESP32 + RFM69HCW + Wi‑Fi con portal)

| Componente | Corriente típica | Uso | Potencia media |
|---|---|---|---|
| ESP32 con Wi‑Fi en modo punto de acceso | ~120 mA a 3,3 V | 24 h (el portal debe estar siempre disponible) | 0,40 W |
| RFM69HCW en recepción | ~16 mA a 3,3 V | 24 h (escucha y reenvía la malla) | 0,05 W |
| RFM69HCW transmitiendo a +20 dBm | ~130 mA a 3,3 V | < 1 % del tiempo (tramas de ~50 ms) | 0,01 W |
| **Subtotal a 3,3 V** | | | **0,46 W** |
| Conversor 12 V → 3,3 V (eficiencia ~85 %) | | | **0,54 W** |

**Energía diaria:** 0,54 W × 24 h ≈ **13 Wh/día**.

### Batería

- Química: **LiFePO4 4S (12,8 V nominal)**. Soporta miles de ciclos, tolera bien el calor y es más
  segura que el ion-litio común: adecuada para quedar instalada en un albergue.
- Autonomía objetivo sin sol: **3 días** (sismo + días nublados en Manizales).
- Profundidad de descarga útil: 80 %.

13 Wh/día × 3 días ÷ 0,8 = **49 Wh** → batería **12,8 V 6 Ah (77 Wh)**, que da ≈ **4,5 días** sin sol.

### Panel solar

- Horas de sol pico en Manizales: ~4 h/día (zona andina con nubosidad frecuente).
- Pérdidas del sistema (controlador, cables, temperatura, suciedad): factor 0,7.

13 Wh ÷ (4 h × 0,7) = 4,6 W para reponer el consumo de un día. Para recargar la batería después
de varios días nublados se duplica o triplica: **panel de 20 W, 12 V**.

### Controlador de carga

Controlador **PWM o MPPT de 10 A para 12 V con perfil LiFePO4** (14,4 V de absorción). El ESP32 mide
el voltaje de la batería y del panel con divisores resistivos (ver `config/README.md`).

### Lista por nodo

| Elemento | Especificación |
|---|---|
| Batería | LiFePO4 12,8 V 6 Ah con BMS |
| Panel | 20 W, 12 V (Voc ~22 V) |
| Controlador | PWM/MPPT 10 A, perfil LiFePO4 |
| Conversor | Buck 12 V → 5 V (USB del ESP32) o 3,3 V, ≥ 1 A |
| Divisores | 100 kΩ/22 kΩ (batería) y 100 kΩ/10 kΩ (panel) |
| Protección | Fusible de 3 A en la batería, caja IP65 |

## 2. Puesto de mando (portátil + gateway)

| Componente | Potencia media | Horas/día | Energía |
|---|---|---|---|
| Portátil con el servidor (pantalla atenuada) | ~30 W | 24 h | 720 Wh |
| Gateway ESP32-S3 + RFM69HCW (por el USB del portátil) | ~0,3 W | 24 h | 7 Wh |
| **Total** | | | **≈ 730 Wh/día** |

Con un **Mini PC** de bajo consumo (~10 W) el total baja a ≈ 250 Wh/día; el portátil, en cambio,
aporta su propia batería como respaldo (UPS natural).

- **Batería:** LiFePO4 12,8 V **100 Ah (1.280 Wh)** → ~1,4 días con el portátil, ~4 días con Mini PC.
- **Panel:** 730 Wh ÷ (4 h × 0,7) ≈ 260 W → **2 paneles de 150 W**.
- **Inversor** 12 V → 110 V de onda senoidal pura de 300 W para el cargador del portátil (o un
  cargador de portátil a 12 V, más eficiente).

## 3. Cómo se ve en el sistema

- Cada trama del nodo trae `BAT_V|PANEL_V|CARGA_PCT`; el servidor guarda la energía de cada nodo.
- El dashboard y la app (pestaña **Energía**) muestran batería, panel y la **autonomía estimada sin
  sol**: `carga% × capacidad útil ÷ consumo`. Con los valores de arriba, un nodo al 100 % muestra
  ≈ 114 h.
- Si la carga baja del 20 %, se genera una alerta de **batería baja** para enviar a alguien a revisar
  el kit.

## 4. Ahorros posibles (si las mediciones salen peores)

- Bajar la potencia de transmisión del Wi‑Fi del ESP32 (`WiFi.setTxPower`) si el albergue es pequeño.
- Apagar el punto de acceso de noche o tras un tiempo sin clientes y reactivarlo con un botón.
- Telemetría cada 10–15 min en vez de 5 cuando la batería esté baja.
