"""Tasmota thermostat."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from .const import (
    COMMAND_TARGET_TEMPERATURE,
    CONF_DEEP_SLEEP,
    CONF_MAC,
)
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .mqtt import ReceiveMessage
from .utils import (
    config_get_state_offline,
    config_get_state_online,
    get_topic_command,
    get_topic_command_state,
    get_topic_stat_result,
    get_topic_tele_state,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TasmotaThermostatConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota thermostat configuation."""

    command_topic: str
    result_topic: str
    state_topic: str

    @classmethod
    def from_discovery_message(cls, config: dict, platform: str) -> TasmotaFanConfig:
        """Instantiate from discovery message."""
        return cls(
            endpoint="climate",
            idx="iclimate",
            friendly_name=None,
            mac=config[CONF_MAC],
            platform=platform,
            poll_payload="",
            poll_topic=get_topic_command_state(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            deep_sleep_enabled=config[CONF_DEEP_SLEEP],
            command_topic=get_topic_command(config),
            result_topic=get_topic_stat_result(config),
            state_topic=get_topic_tele_state(config),
        )


class TasmotaThermostat(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota thermostat."""

    _cfg: TasmotaThermostatConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        super().__init__(**kwds)

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            if not self._on_state_callback:
                return
            target_temperature: int = get_value_by_path(msg.payload, [COMMAND_TARGET_TEMPERATURE])
            self._on_state_callback(target_temperature)

        availability_topics = self.get_availability_topics()
        topics = {
            "result_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.result_topic,
                "msg_callback": state_message_received,
            },
            "state_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic,
                "msg_callback": state_message_received,
            },
        }
        topics = {**topics, **availability_topics}

        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    async def set_target_temperature(self, target_temperature: float) -> None:
        """Set the target temperature."""
        payload = target_temperature
        command = COMMAND_TARGET_TEMPERATURE
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
            retain=True,
        )
