"""
components.verisure
~~~~~~~~~~~~~~~~~~
"""
import logging
from datetime import timedelta

from homeassistant import bootstrap
from homeassistant.loader import get_component

from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED,
    ATTR_SERVICE, ATTR_DISCOVERED,
    CONF_USERNAME, CONF_PASSWORD)


DOMAIN = "verisure"
DISCOVER_SENSORS = 'verisure.sensors'
DISCOVER_SWITCHES = 'verisure.switches'

DEPENDENCIES = []
REQUIREMENTS = [
    'https://github.com/persandstrom/python-verisure/archive/master.zip'
    ]

_LOGGER = logging.getLogger(__name__)

MY_PAGES = None
STATUS = {}

VERISURE_LOGIN_ERROR = None
VERISURE_ERROR = None

# if wrong password was given don't try again
WRONG_PASSWORD_GIVEN = False

MIN_TIME_BETWEEN_REQUESTS = timedelta(seconds=5)


def setup(hass, config):
    """ Setup the Verisure component. """

    if not validate_config(config,
                           {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return False

    from verisure import MyPages, LoginError, Error

    STATUS[MyPages.DEVICE_ALARM] = {}
    STATUS[MyPages.DEVICE_CLIMATE] = {}
    STATUS[MyPages.DEVICE_SMARTPLUG] = {}

    global MY_PAGES
    MY_PAGES = MyPages(
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD])
    global VERISURE_LOGIN_ERROR, VERISURE_ERROR
    VERISURE_LOGIN_ERROR = LoginError
    VERISURE_ERROR = Error

    try:
        MY_PAGES.login()
    except (ConnectionError, Error) as ex:
        _LOGGER.error('Could not log in to verisure mypages, %s', ex)
        return False

    update()

    # Load components for the devices in the ISY controller that we support
    for comp_name, discovery in ((('sensor', DISCOVER_SENSORS),
                                  ('switch', DISCOVER_SWITCHES))):
        component = get_component(comp_name)
        bootstrap.setup_component(hass, component.DOMAIN, config)

        hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                      {ATTR_SERVICE: discovery,
                       ATTR_DISCOVERED: {}})

    return True


def get_alarm_status():
    ''' return a list of status overviews for alarm components '''
    return STATUS[MY_PAGES.DEVICE_ALARM]


def get_climate_status():
    ''' return a list of status overviews for alarm components '''
    return STATUS[MY_PAGES.DEVICE_CLIMATE]


def get_smartplug_status():
    ''' return a list of status overviews for alarm components '''
    return STATUS[MY_PAGES.DEVICE_SMARTPLUG]


def reconnect():
    ''' reconnect to verisure mypages '''
    try:
        MY_PAGES.login()
    except VERISURE_LOGIN_ERROR as ex:
        _LOGGER.error("Could not login to Verisure mypages, %s", ex)
        global WRONG_PASSWORD_GIVEN
        WRONG_PASSWORD_GIVEN = True
    except (ConnectionError, VERISURE_ERROR) as ex:
        _LOGGER.error("Could not login to Verisure mypages, %s", ex)


@Throttle(MIN_TIME_BETWEEN_REQUESTS)
def update():
    ''' Updates the status of verisure components '''
    if WRONG_PASSWORD_GIVEN:
        # Is there any way to inform user?
        return

    try:
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_ALARM):
            STATUS[MY_PAGES.DEVICE_ALARM][overview.id] = overview
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_CLIMATE):
            STATUS[MY_PAGES.DEVICE_CLIMATE][overview.id] = overview
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_SMARTPLUG):
            STATUS[MY_PAGES.DEVICE_SMARTPLUG][overview.id] = overview
    except ConnectionError as ex:
        _LOGGER.error('Caught connection error %s, tries to reconnect', ex)
        reconnect()