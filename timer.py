# -*- coding: utf-8 -*-
"""定時層：睡眠定時器（純邏輯，依賴 Kivy 時鐘）。"""

from kivy.clock import Clock


class SleepTimer:
    def __init__(self, on_tick, on_end):
        self.on_tick = on_tick
        self.on_end = on_end
        self.remaining = 0
        self._evt = None

    def start(self, minutes):
        self.cancel()
        self.remaining = int(minutes) * 60
        self._evt = Clock.schedule_interval(self._tick, 1)

    def cancel(self):
        if self._evt:
            self._evt.cancel()
            self._evt = None
        self.remaining = 0

    def _tick(self, dt):
        self.remaining -= 1
        if self.remaining <= 0:
            self.cancel()
            self.on_end()
            return False
        self.on_tick(self.remaining)
        return True
