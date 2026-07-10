"""
CatSprayer Output Controller
"""

from __future__ import annotations

import time

from catsprayer.config import CONFIG
from catsprayer.gpio_control import GPIOControl



class SprayerController:


    def __init__(
        self,
        spray_duration=None,
        simulation=None
    ):

        if spray_duration is None:

            spray_duration = CONFIG["spray_duration"]


        if simulation is None:

            simulation = CONFIG["simulation"]


        self.spray_duration = spray_duration
        self.simulation = simulation


        if not self.simulation:

            self.gpio = GPIOControl()



    def activate(self):

        print()
        print("====================")
        print(" SPRAYER ON")
        print("====================")
        print()


        if self.simulation:

            time.sleep(
                self.spray_duration
            )


        else:

            self.gpio.on()

            time.sleep(
                self.spray_duration
            )

            self.gpio.off()



        print()
        print("====================")
        print(" SPRAYER OFF")
        print("====================")
        print()



    def cleanup(self):

        if not self.simulation:

            self.gpio.cleanup()
