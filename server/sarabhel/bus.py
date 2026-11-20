"""Cliente del broker MQTT (Mosquitto) compartido por todos los servicios."""
import json
import logging
import time
from typing import Any, Callable

import paho.mqtt.client as mqtt

from . import config

log = logging.getLogger(__name__)
Handler = Callable[[str, dict], None]


class Bus:
    def __init__(self, name: str):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sarabhel-{name}")
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self._handlers: dict[str, Handler] = {}

    def subscribe(self, topic: str, handler: Handler) -> None:
        """Registrar antes de start()/run_forever(); se re-suscribe en cada reconexión."""
        self._handlers[topic] = handler

    def publish(self, topic: str, payload: dict[str, Any], qos: int = 1) -> None:
        self.client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=qos)

    def start(self) -> None:
        """Conecta y atiende la red en un hilo de fondo."""
        self._connect()
        self.client.loop_start()

    def run_forever(self) -> None:
        """Conecta y bloquea atendiendo mensajes (reconecta solo)."""
        self._connect()
        self.client.loop_forever(retry_first_connection=True)

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    # --- internos -------------------------------------------------------
    def _connect(self) -> None:
        while True:
            try:
                self.client.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
                return
            except OSError as exc:
                log.warning("Broker %s:%s no disponible (%s); reintento en 2 s",
                            config.MQTT_HOST, config.MQTT_PORT, exc)
                time.sleep(2)

    def _on_connect(self, client, _userdata, _flags, reason_code, _props):
        if reason_code.is_failure:
            log.error("Conexión rechazada por el broker: %s", reason_code)
            return
        log.info("Conectado al broker %s:%s", config.MQTT_HOST, config.MQTT_PORT)
        for topic in self._handlers:
            client.subscribe(topic, qos=1)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _props):
        if reason_code != 0:
            log.warning("Desconectado del broker (%s); reconectando…", reason_code)

    def _on_message(self, _client, _userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            log.warning("Mensaje no JSON en %s, descartado", msg.topic)
            return
        for pattern, handler in self._handlers.items():
            if mqtt.topic_matches_sub(pattern, msg.topic):
                try:
                    handler(msg.topic, payload)
                except Exception:  # un mensaje malo no debe tumbar el servicio
                    log.exception("Error procesando %s: %r", msg.topic, payload)
