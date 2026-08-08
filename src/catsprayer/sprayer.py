"""
CatSprayer Output Controller
"""

from __future__ import annotations

import threading
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

        # Guards against overlapping GPIO pulses if a second trigger somehow
        # lands while a spray is still in progress -- without this, two
        # overlapping threads could turn the relay off early or leave it
        # stuck on.
        self._spray_lock = threading.Lock()


        if not self.simulation:

            self.gpio = GPIOControl()



    def activate(self):
        """
        Non-blocking: starts the spray pulse on its own thread and returns
        immediately, so the caller (the hardware/detection loop) is never
        stalled for spray_duration seconds. Ignored if a spray is already
        in progress.
        """

        if not self._spray_lock.acquire(blocking=False):
            print("Spray already in progress, ignoring overlapping activation.")
            return

        threading.Thread(target=self._do_spray, daemon=True).start()



    def _do_spray(self):

        try:
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

        finally:
            self._spray_lock.release()



    def cleanup(self):

        if not self.simulation:

            self.gpio.cleanup()
