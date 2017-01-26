# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.


import subprocess
import time

from mycroft.configuration import ConfigurationManager
from mycroft.messagebus.client.ws import WebsocketClient
from mycroft.messagebus.message import Message
from mycroft.util.log import getLogger

logger = getLogger("GpioClient")

try:
   import RPi.GPIO as GPIO
except RuntimeError:
   logger.error("Got runtime error, make sure you are running in sudo mode?")
except ImportError:
   logger.error("Could not load Raspberry Pi's GPIO module. Do you have it installed?")

__author__ = 'thowe'


class Gpio(object):
    """
    Serves as a communication interface for GPIO
    """

    def __init__(self):
        self.ws = WebsocketClient()
        ConfigurationManager.init(self.ws)
        self.config = ConfigurationManager.get().get("gpio")
        self.started = False
        if(GPIO):
            self.init_gpio()
            self.start()

    def init_gpio(self):
        GPIO.setmode(GPIO.BOARD)
        logger.info("GPIO Channel: " + str(self.config['listening_pin']))
        GPIO.setup(self.config['listening_pin'],GPIO.OUT)
        GPIO.setup(self.config['thinking_pin'],GPIO.OUT)
        GPIO.setup(self.config['speaking_pin'],GPIO.OUT)

    def start(self, event=None):
        self.__register_events()
        self.started = True

    def __register_events(self):
        self.ws.on('recognizer_loop:record_begin', self.handle_record_begin)
        self.ws.on('recognizer_loop:record_end', self.handle_record_end)
        self.ws.on('recognizer_loop:audio_output_start', self.handle_audio_output_start)
        self.ws.on('recognizer_loop:audio_output_end', self.handle_audio_output_end)

    def handle_record_begin(self, event=None):
        logger.info("Set Record LED ON...")
        GPIO.output(self.config.listening_gpio_pin,GPIO.HIGH)

    def handle_record_end(self, event=None):
        logger.info("Set Record LED OFF...")
        GPIO.output(self.config.listening_gpio_pin,GPIO.LOW)
        GPIO.output(self.config.listening_gpio_pin,GPIO.LOW)

    def handle_audio_output_start(self, event=None):
        logger.info("Set Audio Output LED ON...")
        GPIO.output(self.config.thinking_gpio_pin,GPIO.LOW)
        GPIO.output(self.config.speaking_gpio_pin,GPIO.HIGH)

    def handle_audio_output_end(self, event=None):
        logger.info("Set Audio Output LED OFF...")
        GPIO.output(self.config.speaking_gpio_pin,GPIO.LOW)


    def run(self):
        try:
            self.ws.run_forever()
        except Exception as e:
            LOG.error("Error: {0}".format(e))
            self.stop()

    def stop(self):
        if not self.started:
            self.ws.close()
