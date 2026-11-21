# Guion de la demo (≈ 5 minutos)

El escenario simula un **sismo en Manizales** que siempre se desarrolla igual, para que la
presentación no dependa de la suerte. Funciona sin hardware y sin internet (salvo el fondo del mapa).

## Preparación (antes de presentar)

1. Portátil con la zona con cobertura activada (o un hotspot) y el teléfono conectado a esa red.
2. En la carpeta `server`:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\iniciar.ps1 -Radio escenario
   ```

   El escenario arranca en cuanto se abre la ventana del listener: inicia el servidor **justo antes
   de empezar** (o ciérralo y vuelve a abrirlo para reiniciar la historia).
3. Proyecta el dashboard: `http://localhost:8080` y entra con un usuario de puesto de mando
   (el primer uso: `admin` / `1234`, ver [USUARIOS.md](USUARIOS.md)).
4. Opcional: un nodo de albergue simulado para la parte del teléfono:
   `server\.venv\Scripts\python firmware\herramientas\nodo_simulado.py --nodo 7 --nombre "Albergue Bosques"`.

## Línea de tiempo

| Seg. | Qué pasa en la pantalla | Qué decir |
|---|---|---|
| 0 | Aparecen 5 nodos de albergue en el mapa, con su batería y panel en **Energía** | “Cayó la red celular y la eléctrica. Cada albergue tiene un nodo de radio de 915 MHz con su propio panel solar.” |
| 3 | Mensaje del **Albergue Coliseo**: sismo fuerte, albergue abierto | “Los reportes llegan por radio, de nodo en nodo, hasta este portátil. Sin internet.” |
| 12 | **Ladera Aranjuez**: derrumbe en la vía | “El sistema clasifica cada mensaje por palabras clave: un derrumbe es crítico.” |
| 20 | Aranjuez **entra a una zona de riesgo** → alerta naranja | “Cruzamos la ubicación GPS con las zonas de amenaza del POT y alertamos automáticamente.” |
| 30 | **SOS** de La Enea: 3 personas atrapadas (mensaje largo) → **alerta crítica** | “Un SOS es crítico. Este mensaje no cabe en un paquete de radio: el nodo lo parte y aquí se reconstruye.” |
| 35 | Clic en la alerta → **Atender** → **👥 Equipo**: “Bomberos 2” | “El puesto de mando asigna un equipo y lleva el seguimiento de cada alerta.” |
| 42 | Chipre: necesitan agua para 120 personas | “Necesidades logísticas: prioridad moderada.” |
| 55 | **Batería baja** en Puesto San José (18 %) | “Monitoreamos la energía de cada kit: sabemos qué albergue se va a quedar sin comunicación antes de que pase, y cuánta autonomía le queda.” |
| 68 | Coliseo: herido con fractura → otra alerta crítica | — |
| 85 | La Enea: rescatadas 2 personas | Marcar la alerta del SOS como **✓ Atendida** y agregar una nota. |
| 100 | Chipre: llegó el agua | — |
| 115 | Fin del guion: sigue la simulación normal | Mostrar **⬇ Alertas CSV**: “Todo queda registrado para entregar a la UNGRD / alcaldía.” |

## Parte con el teléfono (opcional, 1 minuto)

1. En el teléfono, app → **Estoy en campo** → **📡 Wi‑Fi del albergue** → dirección del nodo simulado
   (`http://<ip-del-pc>:8765`).
2. Mantener presionado el **SOS** → aparece en el dashboard como alerta crítica **con la ubicación
   del teléfono** en el mapa.
3. Desde el dashboard, responder al albergue “Bosques” → el mensaje aparece en el teléfono.
4. Mostrar el **portal**: abrir `http://<ip-del-pc>:8765` en el navegador del teléfono — “quien no
   tenga la app ve esta página automáticamente al conectarse al Wi‑Fi del albergue”.

## Si algo falla

- ¿No aparecen nodos? Revisar que la ventana “Listener (escenario de demo)” esté abierta sin errores.
- ¿Para repetir? Cerrar todas las ventanas del servidor y volver a ejecutar `iniciar.ps1 -Radio escenario`.
  Para empezar con el historial limpio, borrar `server\data\sarabhel.db` antes de iniciar.
