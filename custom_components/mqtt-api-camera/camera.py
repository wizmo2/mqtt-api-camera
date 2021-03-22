"""Camera that loads a picture from an API link specified by a MQTT topic."""
import asyncio
import logging

import aiohttp
import async_timeout
import requests
from requests.auth import HTTPDigestAuth

import voluptuous as vol

from homeassistant.components import camera, mqtt
from homeassistant.components.camera import Camera
from homeassistant.const import (
    CONF_DEVICE,
    CONF_NAME,
    CONF_PASSWORD, 
    CONF_USERNAME, 
    CONF_AUTHENTICATION, 
    CONF_VERIFY_SSL, 
    HTTP_BASIC_AUTHENTICATION, 
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

CONF_TOPIC = "topic"
CONF_HOST = "host"
CONF_FRAMERATE = "framerate"

DEFAULT_NAME = "MQTT API Camera"

PLATFORM_SCHEMA = (
    mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
        {
            #vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
            vol.Required(CONF_HOST) : cv.string,
            vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
                [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
            ),            
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_USERNAME): cv.string,
            vol.Optional(CONF_FRAMERATE, default=2): vol.Any(
                cv.small_float, cv.positive_int
            ),            
            vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,        
        }
    )
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a generic IP Camera."""
    async_add_entities([MqttAPICamera(hass, config)])


class MqttAPICamera(Camera):
    """representation of a MQTT camera."""

    def __init__(self, hass, config):
        """Initialize the MQTT Camera."""
        
        super().__init__()
        self.hass = hass 
        self._config = config
        self._name = config.get(CONF_NAME)
        device_config = config.get(CONF_DEVICE)

        self._host = config.get(CONF_HOST)
        self._still_image_url = None
        self._frame_interval = 1 / config[CONF_FRAMERATE]
        self.verify_ssl = config[CONF_VERIFY_SSL]
        username = config.get(CONF_USERNAME)
        password = config.get(CONF_PASSWORD)

        self._authentication = config.get(CONF_AUTHENTICATION)
        if username and password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                self._auth = HTTPDigestAuth(username, password)
            else:
                self._auth = aiohttp.BasicAuth(username, password=password)
        else:
            self._auth = None

        self._last_image = None
        self._last_url = None 
           
    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        
        def message_received(msg):
            """Handle new MQTT messages."""
            self._still_image_url = self._host +  msg.payload.replace('"',"") 
            _LOGGER.info("Updating still image url to '%s'", self._still_image_url)
        
        await mqtt.async_subscribe(
            self.hass, self._config[CONF_TOPIC], message_received, self._config[mqtt.CONF_QOS]
        )
        
    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return self._frame_interval

    @property
    def supported_features(self):
        """Return supported features for this camera. 0 for this camera"""
        return 0

    def camera_image(self):
        """Return bytes of camera image."""
        return asyncio.run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop
        ).result()
    
    async def async_camera_image(self):
        """Return a still image response from the camera."""
        try:
            url = self._still_image_url
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        # aiohttp don't support DigestAuth yet
        if self._authentication == HTTP_DIGEST_AUTHENTICATION:

            def fetch():
                """Read image from a URL."""
                try:
                    response = requests.get(
                        url, timeout=10, auth=self._auth, verify=self.verify_ssl
                    )
                    return response.content
                except requests.exceptions.RequestException as error:
                    _LOGGER.error("Error getting new camera image from %s: %s", self._name, error)
                    return self._last_image

            self._last_image = await self.hass.async_add_job(fetch)
        # async
        else:
            try:
                websession = async_get_clientsession(
                    self.hass, verify_ssl=self.verify_ssl
                )
                with async_timeout.timeout(10):
                    response = await websession.get(url, auth=self._auth)
                self._last_image = await response.read()
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout getting camera image from %s", self._name)
                return self._last_image
            except aiohttp.ClientError as err:
                _LOGGER.error("Error getting new camera image from %s: %s", self._name, err)
                return self._last_image

        self._last_url = url
        return self._last_image

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
        
