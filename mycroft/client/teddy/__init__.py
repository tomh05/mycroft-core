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
from Queue import Queue
from alsaaudio import Mixer
from threading import Thread, Timer

import serial

from mycroft.client.teddy.eyes import TeddyEyes
from mycroft.client.teddy.mouth import TeddyMouth
from mycroft.configuration import ConfigurationManager
from mycroft.messagebus.client.ws import WebsocketClient
from mycroft.messagebus.message import Message
from mycroft.util import play_wav, create_signal
from mycroft.util.audio_test import record
from mycroft.util.log import getLogger

__author__ = 'aatchison', 'jdorleans', 'iward'

LOG = getLogger("TeddyClient")

try:
   import RPi.GPIO as GPIO
except RuntimeError:
   logger.error("Got runtime error, make sure you are running in sudo mode?")
except ImportError:
   logger.error("Could not load Raspberry Pi's GPIO module. Do you have it installed?")


class TeddyWriter(Thread):
    """
    Writes data to Serial port.
        #. Enqueues all commands received from Mycroft teddys
           implementation
        #. Process them on the received order by writing on the Serial port

    E.g. Displaying a text on Mycroft's Mouth
        #. ``TeddyMouth`` sends a text command
        #. ``TeddyWriter`` captures and enqueue the command
        #. ``TeddyWriter`` removes the next command from the queue
        #. ``TeddyWriter`` writes the command to Serial port

    Note: A command has to end with a line break
    """

    def __init__(self, serial, ws, size=16):
        super(TeddyWriter, self).__init__(target=self.flush)
        self.alive = True
        self.daemon = True
        self.serial = serial
        self.ws = ws
        self.commands = Queue(size)
        self.init_stepper();
        self.start()

    def init_stepper(self, pin1, pin2, pin3, pin4):
        GPIO.setmode(GPIO.BCM)
        self.steps=[[1,0,1,0],[0,1,1,0],[0,1,0,1],[1,0,0,1]]
        for pin in self.config['pins']
           GPIO.setup(pin,GPIO.OUT)
        self.calibrate_motor()

    def calibrate_motor(self):
        for i in range(100):
           step("clockwise",10)


    def step(self,direction,delay):
        if (direction == "clockwise")
            for step_pins in steps:
                self.set_step(step_pins)
                time.sleep(delay)
        else:
            for step_pins in reversed(steps):
                self.set_step(step_pins)
                time.sleep(delay)


    def set_step(self,pins);
        for pin in pins:
            GPIO.output(self.config['pins'][pin],pins[pin])

    def flush(self):
        while self.alive:
            try:
                cmd = self.commands.get()
                self.serial.write(cmd + '\n')
                LOG.info("Writing: " + cmd)
                self.commands.task_done()
            except Exception as e:
                LOG.error("Writing error: {0}".format(e))

    def write(self, command):
        self.commands.put(str(command))

    def stop(self):
        self.alive = False


class Teddy(object):
    """
    Serves as a communication interface between Arduino and Mycroft Core.

    ``Teddy`` initializes and aggregates all teddys implementation.

    E.g. ``TeddyEyes``, ``TeddyMouth`` and ``TeddyArduino``

    It also listens to the basis events in order to perform those core actions
    on the unit.

    E.g. Start and Stop talk animation
    """

    def __init__(self):
        self.ws = WebsocketClient()
        ConfigurationManager.init(self.ws)
        self.config = ConfigurationManager.get().get("teddy")
        self.__init_serial()
        self.writer = TeddyWriter(self.serial, self.ws)
        self.ws.on("teddy.start", self.start)
        self.started = False
        Timer(5, self.stop).start()     # WHY? This at least needs an explaination, this is non-obvious behavior

    def start(self, event=None):
        self.eyes = TeddyEyes(self.ws, self.writer)
        self.mouth = TeddyMouth(self.ws, self.writer)
        self.__register_events()
        self.__reset()
        self.started = True

    def __init_serial(self):
        try:
            self.port = self.config.get("port")
            self.rate = self.config.get("rate")
            self.timeout = self.config.get("timeout")
            self.serial = serial.serial_for_url(
                url=self.port, baudrate=self.rate, timeout=self.timeout)
            LOG.info("Connected to: %s rate: %s timeout: %s" %
                     (self.port, self.rate, self.timeout))
        except:
            LOG.error("Impossible to connect to serial port: " + self.port)
            raise

    def __register_events(self):
        self.ws.on('teddy.mouth.events.activate',
                   self.__register_mouth_events)
        self.ws.on('teddy.mouth.events.deactivate',
                   self.__remove_mouth_events)
        self.ws.on('teddy.reset',
                   self.__reset)
        self.__register_mouth_events()

    def __register_mouth_events(self, event=None):
        self.ws.on('recognizer_loop:record_begin', self.mouth.listen)
        self.ws.on('recognizer_loop:record_end', self.mouth.reset)
        self.ws.on('recognizer_loop:audio_output_start', self.mouth.talk)
        self.ws.on('recognizer_loop:audio_output_end', self.mouth.reset)

    def __remove_mouth_events(self, event=None):
        self.ws.remove('recognizer_loop:record_begin', self.mouth.listen)
        self.ws.remove('recognizer_loop:record_end', self.mouth.reset)
        self.ws.remove('recognizer_loop:audio_output_start',
                       self.mouth.talk)
        self.ws.remove('recognizer_loop:audio_output_end',
                       self.mouth.reset)

    def __reset(self, event=None):
        # Reset both the mouth and the eye elements to indicate the unit is
        # ready for input.
        self.writer.write("eyes.reset")
        self.writer.write("mouth.reset")

    def speak(self, text):
        self.ws.emit(Message("speak", {'utterance': text}))

    def run(self):
        try:
            self.ws.run_forever()
        except Exception as e:
            LOG.error("Error: {0}".format(e))
            self.stop()

    def stop(self):
        if not self.started:
            self.writer.stop()
            self.serial.close()
            self.ws.close()
