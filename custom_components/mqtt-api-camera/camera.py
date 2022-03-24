"""Camera that loads a picture from an API link specified by a MQTT topic."""
from __future__ import annotations
import logging

import httpx
import voluptuous as vol
from urllib.parse import urljoin

from homeassistant.components import mqtt
from homeassistant.components.camera import DEFAULT_CONTENT_TYPE,Camera
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.reload import async_setup_reload_service

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONF_TOPIC = "topic"
CONF_HOST = "host"
CONF_CONTENT_TYPE = "content_type"
CONF_FRAMERATE = "framerate"

DEFAULT_NAME = "MQTT API Camera"
GET_IMAGE_TIMEOUT = 10

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        # vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_CONTENT_TYPE, default=DEFAULT_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_FRAMERATE, default=2): vol.Any(
            cv.small_float, cv.positive_int
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a generic IP Camera."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    async_add_entities([MqttAPICamera(hass, config)])


class MqttAPICamera(Camera):
    """representation of a MQTT camera."""

    def __init__(self, hass, device_info):
        """Initialize the MQTT Camera."""

        super().__init__()
        self.hass = hass
        self._config = device_info
        self._authentication = device_info.get(CONF_AUTHENTICATION)
        self._name = device_info.get(CONF_NAME)
        self._host = device_info.get(CONF_HOST)
        self._still_image_url = None
        self._frame_interval = 1 / device_info[CONF_FRAMERATE]
        self._supported_features = 0
        self.content_type = device_info[CONF_CONTENT_TYPE]
        self.verify_ssl = device_info[CONF_VERIFY_SSL]
        username = device_info.get(CONF_USERNAME)
        password = device_info.get(CONF_PASSWORD)

        if username and password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                self._auth = httpx.DigestAuth(username=username, password=password)
            else:
                self._auth = httpx.BasicAuth(username=username, password=password)
        else:
            self._auth = None

        self._last_image = None
        self._last_url = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""

        def message_received(msg):
            """Handle new MQTT messages."""
            self._still_image_url = urljoin(self._host, msg.payload.replace('"', ""))
            _LOGGER.info("Updating still image url to '%s'", self._still_image_url)

        await mqtt.async_subscribe(
            self.hass,
            self._config[CONF_TOPIC],
            message_received,
            self._config[mqtt.CONF_QOS],
        )

    @property
    def supported_features(self):
        """Return supported features for this camera."""
        return self._supported_features

    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return self._frame_interval

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        try:
            url = self._still_image_url
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        try:
            async_client = get_async_client(self.hass, verify_ssl=self.verify_ssl)
            response = await async_client.get(
                url, auth=self._auth, timeout=GET_IMAGE_TIMEOUT
            )
            response.raise_for_status()
            self._last_image = response.content
        except httpx.TimeoutException:
            _LOGGER.error("Timeout getting camera image from %s", self._name)
            return self._last_image
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.error("Error getting new camera image from %s: %s", self._name, err)
            return self._last_image

        self._last_url = url
        return self._last_image

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
