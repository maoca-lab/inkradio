# -*- coding: utf-8 -*-
"""
音訊層（AudioEngine）：跨平台播放的協調者。

依平台選擇後端：
  - 安卓 → android_player.AndroidPlayer（原生 MediaPlayer + Equalizer）
  - 桌面 → Kivy SoundLoader

對外只暴露統一介面（play_url / toggle / pause / set_volume / eq_*），
UI 層不需知道目前跑在哪一個平台上。
"""

import os
from kivy.utils import platform
from android_player import AndroidPlayer


class AudioEngine:
    def __init__(self):
        self.volume = 0.8
        self.muted = False
        self.playing = False
        self.current_url = None
        self._state_cb = []
        self._use_native = (platform == "android")
        self._sound = None
        self._backend = AndroidPlayer(self._emit) if self._use_native else None

    def on_state(self, cb):
        self._state_cb.append(cb)

    def _emit(self, state):
        for cb in self._state_cb:
            try:
                cb(state)
            except Exception:
                pass

    # ---- 對外 API ----
    def play_url(self, url):
        self.current_url = url
        self.playing = False
        if self._use_native:
            self._backend.play(url)
            self._backend.apply_volume(self.volume, self.muted)
        else:
            self._sdl_play(url)

    def _sdl_play(self, url):
        from kivy.core.audio import SoundLoader
        if self._sound:
            try:
                self._sound.stop()
            except Exception:
                pass
        self._sound = SoundLoader.load(url)
        if self._sound:
            self._sound.volume = 0.0 if self.muted else self.volume
            self._sound.play()
            self.playing = True
            self._emit("playing")
        else:
            self.playing = False
            self._emit("error")

    def toggle(self):
        if self.playing:
            self.pause()
        elif self.current_url:
            self.play_url(self.current_url)

    def pause(self):
        if self._use_native and self._backend:
            self._backend.pause()
        elif self._sound:
            try:
                self._sound.stop()
            except Exception:
                pass
        self.playing = False
        self._emit("paused")

    def stop(self):
        self.pause()

    def set_volume(self, v):
        self.volume = max(0.0, min(1.0, v))
        if self._use_native and self._backend:
            self._backend.apply_volume(self.volume, self.muted)
        elif self._sound:
            self._sound.volume = 0.0 if self.muted else self.volume

    def set_muted(self, m):
        self.muted = m
        if self._use_native and self._backend:
            self._backend.apply_volume(self.volume, self.muted)
        elif self._sound:
            self._sound.volume = 0.0 if m else self.volume

    # ---- Equalizer 代理（僅安卓後端支援） ----
    def eq_available(self):
        return self._backend.eq_available() if self._backend else False

    def eq_band_count(self):
        return self._backend.eq_band_count() if self._backend else 0

    def eq_band_center(self, b):
        return self._backend.eq_band_center(b) if self._backend else 0

    def eq_range(self):
        return self._backend.eq_range() if self._backend else (-1500, 1500)

    def set_eq_band(self, band, milli_db):
        if self._backend:
            self._backend.set_eq_band(band, milli_db)

    def reset_eq(self):
        if self._backend:
            self._backend.reset_eq()
