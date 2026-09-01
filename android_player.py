# -*- coding: utf-8 -*-
"""
安卓平台邊界（Ports & Adapters 中的「Adapter」層）。

本模組集中所有 jnius / Android SDK 呼叫（MediaPlayer、Equalizer、權限、
開機廣播等）。上層 AudioEngine 與 UI 不直接碰安卓 API，只透過這裡的
類別介面操作。這樣平台相關的 bug 被限制在單一檔案，便於維護與替換。
"""

from kivy.clock import Clock
from kivy.app import App


class AndroidPlayer:
    """封裝安卓 MediaPlayer + Equalizer，對外暴露簡單的播放 / EQ 介面。"""

    def __init__(self, on_state):
        self.on_state = on_state          # 播放狀態回呼（來自 AudioEngine._emit）
        self.mp = None
        self._eq = None
        self._eq_global = False           # 是否使用全域 EQ
        self._eq_bands = 0
        self._eq_min = -1500
        self._eq_max = 1500
        self._eq_center = []             # 各頻段中心頻率（Hz）
        self._eq_error = None            # 初始化失敗原因
        self._init_native()

    # ---- 原生播放路徑 ----
    def _init_native(self):
        from jnius import autoclass, PythonJavaClass, java_method
        self._autoclass = autoclass
        self._PythonJavaClass = PythonJavaClass
        self._java_method = java_method
        self.MediaPlayer = autoclass("android.media.MediaPlayer")
        self.Uri = autoclass("android.net.Uri")
        self.PythonActivity = autoclass("org.kivy.android.PythonActivity")

        class _OnPrepared(PythonJavaClass):
            __javainterfaces__ = ["android/media/MediaPlayer$OnPreparedListener"]
            def __init__(self, eng):
                super().__init__(); self.eng = eng
            @java_method("(Landroid/media/MediaPlayer;)V")
            def onPrepared(self, mp):
                try:
                    mp.start()
                except Exception:
                    pass
                self.eng.playing = True
                self.eng.on_state("playing")
                self.eng.setup_eq()       # 準備完成後掛上 Equalizer

        class _OnError(PythonJavaClass):
            __javainterfaces__ = ["android/media/MediaPlayer$OnErrorListener"]
            def __init__(self, eng):
                super().__init__(); self.eng = eng
            @java_method("(Landroid/media/MediaPlayer;II)Z")
            def onError(self, mp, what, extra):
                self.eng.playing = False
                self.eng.on_state("error")
                return True

        self._OnPrepared = _OnPrepared
        self._OnError = _OnError

    def play(self, url):
        if self.mp:
            try:
                self.mp.release()
            except Exception:
                pass
        self._release_eq()
        self.mp = self.MediaPlayer()
        self.mp.setOnPreparedListener(self._OnPrepared(self))
        self.mp.setOnErrorListener(self._OnError(self))
        uri = self.Uri.parse(url)
        self.mp.setDataSource(self.PythonActivity.mActivity, uri)
        self.mp.prepareAsync()

    def apply_volume(self, volume=0.8, muted=False):
        if self.mp:
            v = 0.0 if muted else volume
            try:
                self.mp.setVolume(v, v)
            except Exception:
                pass

    def pause(self):
        if self.mp:
            try:
                self.mp.pause()
            except Exception:
                pass

    def release(self):
        if self.mp:
            try:
                self.mp.release()
            except Exception:
                pass
            self.mp = None
        self._release_eq()

    def _release_eq(self):
        if self._eq:
            try:
                self._eq.release()
            except Exception:
                pass
        self._eq = None
        self._eq_global = False

    # ---- Equalizer（安卓） ----
    def setup_eq(self, retry=0):
        if not self.mp:
            self._eq_error = "播放器尚未準備好"
            self._notify_eq_ui()
            return
        try:
            session = self.mp.getAudioSessionId()
            if session == 0:
                if retry < 15:
                    Clock.schedule_once(lambda dt: self.setup_eq(retry + 1), 0.8)
                    return
                else:
                    self._eq_error = "無法取得 AudioSessionId（播放器尚未準備好）"
                    self._notify_eq_ui()
                    return
            Equalizer = self._autoclass("android.media.audiofx.Equalizer")
            try:
                eq = Equalizer(0, session)
                eq.setEnabled(True)
            except Exception as e1:
                # 若指定 session 失敗，嘗試全域音效（session 0）
                try:
                    eq = Equalizer(0, 0)
                    eq.setEnabled(True)
                    self._eq_global = True
                except Exception as e2:
                    raise RuntimeError("session=%s: %s; global=0: %s" % (session, e1, e2))
            self._eq = eq
            self._eq_bands = int(eq.getNumberOfBands())
            rng = eq.getBandLevelRange()
            self._eq_min = int(rng[0]); self._eq_max = int(rng[1])
            self._eq_center = []
            for b in range(self._eq_bands):
                cf = int(eq.getCenterFreq(b)) // 1000   # milliHz → Hz
                self._eq_center.append(cf)
            self._eq_error = None
            self._notify_eq_ui()
        except Exception as e:
            self._eq = None
            # 若初始化失敗，稍後重試（有時播放器剛開始還沒準備好）
            if retry < 15:
                Clock.schedule_once(lambda dt: self.setup_eq(retry + 1), 0.8)
                return
            self._eq_error = "EQ 初始化失敗: " + str(e)
            print(self._eq_error)
            self._notify_eq_ui()

    def _notify_eq_ui(self):
        """EQ 初始化完成後主動通知 UI 刷新。"""
        try:
            app = App.get_running_app()
            if app and hasattr(app, 'root') and app.root:
                root = app.root
                root._eq_initializing = False
                Clock.schedule_once(lambda dt: root._ensure_eq_sliders(), 0)
        except Exception:
            pass

    def eq_available(self):
        return self._eq is not None

    def eq_band_count(self):
        return self._eq_bands

    def eq_band_center(self, b):
        return self._eq_center[b] if b < len(self._eq_center) else 0

    def eq_range(self):
        return self._eq_min, self._eq_max

    def set_eq_band(self, band, milli_db):
        if self._eq:
            try:
                self._eq.setBandLevel(int(band), int(milli_db))
            except Exception:
                pass

    def reset_eq(self):
        if self._eq:
            try:
                for b in range(self._eq_bands):
                    self._eq.setBandLevel(b, 0)
            except Exception:
                pass


def play_recording(path):
    """用原生 MediaPlayer 播放已錄製的 WAV（平台邊界）。失敗時拋出例外。"""
    from jnius import autoclass
    Uri = autoclass("android.net.Uri")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    mp = autoclass("android.media.MediaPlayer")()
    mp.setDataSource(PythonActivity.mActivity, Uri.parse("file://" + path))
    mp.prepare()
    mp.start()
