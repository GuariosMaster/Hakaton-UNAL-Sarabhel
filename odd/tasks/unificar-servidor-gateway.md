# Unify `server/` as the single gateway-connected system

Branch: `main` (user constraint: work on current branch, no push) | Delivery: `ask-on-risk` | Test runner: `python3 -m unittest discover -s server/tests -v`

## Specs

S1. User: "busques inconsistencias, que no toques configuraciones importantes que nos pueden servir"
- Authorized scope: fix only inconsistencies backed by concrete evidence in `server/`.
- Preserve as-is unless a concrete error is proven: `server/.env.example`, `server/zones/zonas_riesgo.geojson`, `server/mosquitto/mosquitto.conf`, existing ports (`8080`), credentials and radio settings in `config/meshtastic.example.yaml`.
- Checks: `git diff --stat`; review every changed file against this preservation list.

S2. User: "que lo conectes correctamente al gateway conectado, donde se pueda ver los nodos reales"
- The RAK4631 gateway is attached at `/dev/ttyACM0` (verified with `meshtastic --port /dev/ttyACM0 --info`). The USB CDC port belongs to one Listener only.
- The serial override must default to `/dev/ttyACM0` and grant the container access to the host device group (host GID 984 on this machine, overridable).
- Real nodes from the gateway node DB, including battery/voltage, must reach `/api/nodes` and the dashboard. The single live node `!7996c8bb` has `position: {}`; absence of GPS must be shown honestly ("sin GPS"), never invented.
- The MQTT broker stays internal to Docker Compose: no published host port `1883`.
- Checks: `docker compose -f server/docker-compose.yml -f server/docker-compose.serial.yml config` succeeds, has no `1883` host binding, and maps `/dev/ttyACM0`; unit tests for node DB translation.

S3. User: "y las gestiones de alertas, mensajes, etc."
- Critical messages and geofence alerts must keep flowing to `/api/messages`, `/api/stream` and the Alerts panel.
- Mesh retries must not duplicate stored messages: dedupe on Meshtastic `packet_id` with an application-level check under the existing service lock (no destructive schema/data migration).
- Checks: unit test proving a repeated `packet_id` inserts only one message and emits one event.

S4. User: "Necesito todo organizado para que funcione como si fuera un solo sistema."
- Use the previously agreed canonical MQTT topic contract for radio traffic: `lora/gateway/rx/*`, `lora/gateway/tx`, `lora/nodes`. Keep internal `events/*` topics for processed dashboard events, with an explicit topic→SSE-kind map so renaming cannot break the live UI.
- Keep the Python services, broker, SQLite, API and offline Leaflet UI as one coherent stack; docs must match the code.
- Checks: unit test asserting canonical topic constants; SSE mapping covered by code readback.

S5. Assumption (established constraint, not a new user requirement): "DEMO/simulado siempre marcado como tal; no inventar datos ni cifras."
- Default `MESH_CONNECTION=sim` remains the safe fallback, but the dashboard must display an unmistakable DEMO banner sourced from the server's actual connection mode. Real mode must not show the banner.
- Checks: `/api/config` exposes `mesh_connection` and `demo`; UI code consumes it; tests assert the flag logic.

S6. Verification and delivery
- Convert the existing pytest-style tests to stdlib `unittest` so they run without adding a dependency (pytest and `paho` are absent from the host Python), and add regression tests for the new rules.
- Docs (`server/README.md`) must describe the real USB command, GID discovery, the internal broker, canonical topics, the DEMO marker and the unittest runner.
- Checks: `python3 -m unittest discover -s server/tests -v` (in an environment with `requirements.txt` installed), `docker compose config`, `git diff --check`, and `gentle-ai review assess --cwd <repo> --agent opencode --json`.

## Tasks

- T1 | S1,S2,S6 | inline | done | Serial gateway wiring, broker isolation, real node telemetry, preserved config untouched. Risk: item 5 (delivery/environment — compose and device access); verified by independent verifier.
- T2 | S3,S4 | inline | done | Canonical topics, SSE kind mapping, `packet_id` dedupe, regression tests. Risk: none (all consumers are in-repo and updated together).
- T3 | S5 | inline | done | DEMO banner end-to-end (config → API → HTML/CSS/JS). Risk: none.
- T4 | S1,S4,S6 | inline | done | Docs and final verification; corrected README MQTT key after verification blocker. Risk: none.

## Log

L1 (user request, verbatim): "Muy bien, esa prueba la moví, quiero que mires el servidor en la carpeta @PROYECTO/server/ necesito que busques inconsistencias, que no toques configuraciones importantes que nos pueden servir, y que lo conectes correctamente al gateway conectado, donde se pueda ver los nodos reales, y las gestiones de alertas, mensajes, etc. Necesito todo organizado para que funcione como si fuera un solo sistema."

L2 (explorer handoff evidence): topics are `mesh/*` + `events/*`, not the agreed `lora/*`; compose publishes `127.0.0.1:1883:1883`; `packet_id` is stored without dedupe; simulator is the default and has no visible DEMO marker; serial override defaults to `/dev/ttyUSB0` while the live device is `/dev/ttyACM0` with host GID 984.

L3 (verified on host): `meshtastic --port /dev/ttyACM0 --info` → Owner `Meshtastic c8bb (c8bb)`, firmware `2.7.26.54e0d8d`, `nodedbCount 1`, node `!7996c8bb` with `position: {}`, `batteryLevel 101`, `voltage 4.259`. `docker` is installed; `pytest` and `paho` are not installed in host Python.

L4 (user decision): wait for the explorer handoff before editing; received and acted on.

L5 (verification evidence): `PYTHONPATH=server python3 -m unittest discover -s server/tests -v` → 12 tests OK; `python3 -m compileall -q server/sarabhel server/tests` → exit 0; `git diff --check` → exit 0; `yaml.safe_load` of both compose files → exit 0; `node --check server/sarabhel/static/app.js` → exit 0. `docker compose` plugin and `docker-compose` binary are absent, so runtime container validation is UNAVAILABLE.

L6 (RDD): assessed `medium`, `review_due: false` (`under_budget`) after declaring the single untracked feature document. No native review transaction started.

L7 (independent verifier): S1/S2/S3/S5 PASS; S4 initially FAIL on a change-caused docs defect — `server/README.md:105` said `config.mqtt.enabled` while the preserved `config/meshtastic.example.yaml` nests it under `module_config.mqtt.enabled`. Corrected, plus stale `mesh/rx|tx` docstrings in listener/messaging/location. Recheck: 12 tests OK, no stale topic references, README key matches the preserved example. S6 partially UNAVAILABLE (compose runtime). Scratch `/tmp/verify-unify-gateway.7rHwhf` removed by parent.

L8 (memory mirror): pending — Engram reported ambiguous projects (`lora-hakaton`, `unal`) for this workspace; no project key was guessed. Local feature document is authoritative.
