"""Representation of Tier Nearest Scooter Sensors."""

from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_BATTERY_LEVEL,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    LENGTH_METERS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.location import distance

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

DEFAULT_NAME = "Tier Nearest Scooter"
DEFAULT_RADIUS = 500

ICON = "mdi:scooter"
ATTRIBUTION = "Data provided by Tier"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_RADIUS): cv.Number,
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME, DEFAULT_NAME)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    radius = config.get(CONF_RADIUS, DEFAULT_RADIUS)

    api = TierNearestScooterApi(api_key)
    add_entities([TierNearestScooterSensor(api, name, latitude, longitude, radius)])


class TierNearestScooterApi:
    """Representation of the Tier API."""

    def __init__(self, api_key):
        """Initialize the Tier API."""
        self._api_key = api_key

    def get_vehicles(self, latitude, longitude, radius):
        """Get vehicles matching a location and a perimeter from the Tier API."""
        headers = {"x-api-key": self._api_key}
        resource = (
            f"https://platform.tier-services.io/vehicle"
            f"?lat={latitude}"
            f"&lng={longitude}"
            f"&radius={radius}"
        )
        try:
            response = requests.get(resource, headers=headers, verify=True, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s failed with %s", resource, ex)
            return None
        except ValueError as ex:
            _LOGGER.error("Error parsing data: %s failed with %s", resource, ex)
            return None


class TierNearestScooterSensor(Entity):
    """Representation of a Tier Nearest Scooter Sensor."""

    def __init__(self, api, name, latitude, longitude, radius):
        """Initialize the Tier Nearest Scooter Sensor."""
        self._api = api
        self._name = name
        self._latitude = latitude
        self._longitude = longitude
        self._radius = radius
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the Tier Nearest Scooter Sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the Tier Nearest Scooter Sensor."""
        return LENGTH_METERS

    @property
    def icon(self):
        """Icon to use in the frontend of the Tier Nearest Scooter Sensor."""
        return ICON

    @property
    def state(self):
        """Return the state of the Tier Nearest Scooter Sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the Tier Nearest Scooter Sensor."""
        return self._attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the Tier Nearest Scooter Sensor."""
        self._attributes = {}
        self._state = None
        vehicles = {}

        result = self._api.get_vehicles(self._latitude, self._longitude, self._radius)

        if result:
            try:
                vehicles = result["data"]
            except KeyError as ex:
                _LOGGER.error(
                    "Erroneous result found when expecting list of vehicles: %s", ex
                )
        else:
            _LOGGER.error("Empty result found when expecting list of vehicles")

        if vehicles:
            for vehicle in vehicles:
                vehicle["distance"] = distance(
                    vehicle["lat"], vehicle["lng"], self._latitude, self._longitude
                )

            scooter = sorted(vehicles, key=lambda item: item["distance"])[0]

            self._state = round(scooter["distance"])
            self._attributes[ATTR_LATITUDE] = round(scooter["lat"], 5)
            self._attributes[ATTR_LONGITUDE] = round(scooter["lng"], 5)
            self._attributes[ATTR_BATTERY_LEVEL] = round(scooter["batteryLevel"])
            self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
