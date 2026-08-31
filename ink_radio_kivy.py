# -*- coding: utf-8 -*-
"""
水墨風格網路電台 · 安卓原生 App（Kivy 實作，含 EQ / 錄音 / 開機自播）
=========================================================================
單一 Python 檔，採組合式模組化架構：

  1. StationStore  —— 資料層：電台典藏 CRUD、去重、JSON 持久化、匯入/匯出
  2. AudioEngine   —— 音訊層：跨平台播放 + 安卓原生 Equalizer
  3. Recorder      —— 錄音層：安卓麥克風 AudioRecord → WAV 匯出
  4. SleepTimer    —— 定時層：倒數，歸零自動暫停
  5. InkRadio      —— 介面層：水墨 UI 與事件綁定
  6. BootReceiver  —— 開機自播：Java 廣播接收器 + 偏好設定

視覺：宣紙米白 #f5f2eb / 淺墨紙 #eae5d9 / 印章朱砂紅 #c23a2b / 濃墨黑 #2b2b2b

執行（桌面測試）：pip install kivy && python ink_radio_kivy.py
打包 APK：見 README_packaging.md 與 colab_build_apk.ipynb
"""

import os
import json
import uuid
import time
import threading
import wave

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform   # 'android' / 'win' / 'linux' / 'macosx'
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.core.text import LabelBase

# 註冊中文字體，避免中文在 APK 內顯示為方塊
# 字體檔會隨 APK 一起打包（見 buildozer.spec source.include_exts）
LabelBase.register(name='NotoSansCJK',
                   fn_regular='NotoSansCJK-Regular.ttc')
Label.font_name = 'NotoSansCJK'
Button.font_name = 'NotoSansCJK'


# ============================================================
# 1. 資料層：電台典藏庫
# ============================================================
class StationStore:
    def __init__(self):
        try:
            base = App.get_running_app().user_data_dir
        except Exception:
            base = os.getcwd()
        self.base = base
        self.path = os.path.join(base, "stations.json")
        self.stations = self._load()
        self._seed_defaults()

    def _load(self):
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.stations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("儲存失敗:", e)

    def _seed_defaults(self):
        """首次啟動預置「綠邨電台直播」預設頻道（唯讀）。"""
        defaults = [("綠邨電台直播", "https://macaofm995.com/hls1/fm995.m3u8")]
        for name, url in defaults:
            exists = any(s["name"] == name or s["url"] == url
                         for s in self.stations)
            if not exists:
                self.stations.append({
                    "id": str(uuid.uuid4()), "name": name, "url": url,
                    "preset": True,
                })
                self._save()

    def add(self, name, url):
        name = (name or "").strip()
        url = (url or "").strip()
        if not name or not url:
            return False, "名稱與網址皆不可為空"
        for s in self.stations:
            if s["name"] == name or s["url"] == url:
                return False, "電台已存在（名稱或網址重複）"
        self.stations.append({"id": str(uuid.uuid4()), "name": name, "url": url})
        self._save()
        return True, "已典藏"

    def remove(self, sid):
        before = len(self.stations)
        self.stations = [s for s in self.stations if s["id"] != sid]
        if len(self.stations) != before:
            self._save()
            return True
        return False

    def find(self, sid):
        return next((s for s in self.stations if s["id"] == sid), None)

    def export_to(self, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.stations, f, ensure_ascii=False, indent=2)

    def import_from(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                incoming = json.load(f)
        except Exception as e:
            return 0, "檔案讀取失敗:" + str(e)
        if not isinstance(incoming, list):
            return 0, "格式錯誤：頂層需為陣列"
        added = 0
        names = {s["name"] for s in self.stations}
        urls = {s["url"] for s in self.stations}
        for item in incoming:
            name = (item.get("name") or "").strip()
            url = (item.get("url") or "").strip()
            if not name or not url:
                continue
            if name in names or url in urls:
                continue
            self.stations.append({"id": str(uuid.uuid4()), "name": name, "url": url})
            names.add(name); urls.add(url); added += 1
        if added:
            self._save()
        return added, "匯入完成，新增 %d 筆" % added


# ============================================================
# 2. 音訊層：跨平台播放 + 安卓 Equalizer
# ============================================================
class AudioEngine:
    def __init__(self):
        self.volume = 0.8
        self.muted = False
        self.playing = False
        self.current_url = None
        self._state_cb = []
        self._use_native = (platform == "android")
        self._sound = None
        self._mp = None
        # Equalizer 狀態（僅安卓）
        self._eq = None
        self._eq_bands = 0
        self._eq_min = -1500
        self._eq_max = 1500
        self._eq_center = []   # 各頻段中心頻率（Hz）
        self._eq_error = None  # 初始化失敗原因

        if self._use_native:
            self._init_native()

    def on_state(self, cb):
        self._state_cb.append(cb)

    def _emit(self, state):
        for cb in self._state_cb:
            try:
                cb(state)
            except Exception:
                pass

    # ---- 原生（安卓）播放路徑 ----
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
                self.eng._setup_eq()       # 準備完成後掛上 Equalizer
                self.eng._emit("playing")

        class _OnError(PythonJavaClass):
            __javainterfaces__ = ["android/media/MediaPlayer$OnErrorListener"]
            def __init__(self, eng):
                super().__init__(); self.eng = eng
            @java_method("(Landroid/media/MediaPlayer;II)Z")
            def onError(self, mp, what, extra):
                self.eng.playing = False
                self.eng._emit("error")
                return True

        self._OnPrepared = _OnPrepared
        self._OnError = _OnError

    def _native_play(self, url):
        if self._mp:
            try:
                self._mp.release()
            except Exception:
                pass
            self._eq = None
        self._mp = self.MediaPlayer()
        self._mp.setOnPreparedListener(self._OnPrepared(self))
        self._mp.setOnErrorListener(self._OnError(self))
        uri = self.Uri.parse(url)
        self._mp.setDataSource(self.PythonActivity.mActivity, uri)
        self._apply_native_volume()
        self._mp.prepareAsync()

    def _apply_native_volume(self):
        if self._mp:
            v = 0.0 if self.muted else self.volume
            try:
                self._mp.setVolume(v, v)
            except Exception:
                pass

    # ---- Equalizer（安卓） ----
    def _setup_eq(self, retry=0):
        if not self._use_native or not self._mp:
            self._eq_error = "非安卓環境，無法使用 EQ"
            self._notify_eq_ui()
            return
        try:
            session = self._mp.getAudioSessionId()
            if session == 0:
                if retry < 5:
                    # 某些裝置 session id 延遲取得，稍後再試
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self._setup_eq(retry + 1), 0.5)
                    return
                else:
                    self._eq_error = "無法取得 AudioSessionId（播放器尚未準備好）"
                    self._notify_eq_ui()
                    return
            Equalizer = self._autoclass("android.media.audiofx.Equalizer")
            eq = Equalizer(0, session)
            eq.setEnabled(True)
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
            self._eq_error = "EQ 初始化失敗: " + str(e)
            print(self._eq_error)
            self._notify_eq_ui()

    def _notify_eq_ui(self):
        """EQ 初始化完成後主動通知 UI 刷新。"""
        try:
            from kivy.app import App
            from kivy.clock import Clock
            app = App.get_running_app()
            if app and hasattr(app, 'root') and app.root:
                root = app.root
                # 強制允許重建，避免被並發保護擋掉
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

    # ---- 桌面播放路徑 ----
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

    # ---- 對外 API ----
    def play_url(self, url):
        self.current_url = url
        self.playing = False
        if self._use_native:
            self._native_play(url)
        else:
            self._sdl_play(url)

    def toggle(self):
        if self.playing:
            self.pause()
        elif self.current_url:
            self.play_url(self.current_url)

    def pause(self):
        if self._use_native and self._mp:
            try:
                self._mp.pause()
            except Exception:
                pass
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
        if self._use_native:
            self._apply_native_volume()
        elif self._sound:
            self._sound.volume = 0.0 if self.muted else self.volume

    def set_muted(self, m):
        self.muted = m
        if self._use_native:
            self._apply_native_volume()
        elif self._sound:
            self._sound.volume = 0.0 if m else self.volume


# ============================================================
# 3. 錄音層：安卓麥克風 → WAV
# ============================================================
class Recorder:
    """安卓原生 AudioRecord 錄製麥克風，寫入 16-bit PCM WAV。桌面不支援。"""

    def __init__(self, on_state):
        self.on_state = on_state
        self.recording = False
        self._thread = None
        self._rec = None
        self._path = None
        self._start = 0

    def is_recording(self):
        return self.recording

    def elapsed(self):
        return int(time.time() - self._start) if self.recording else 0

    def start(self, path):
        if platform != "android":
            self.on_state("錄音僅限安卓")
            return False
        try:
            from jnius import autoclass
            AudioRecord = autoclass("android.media.AudioRecord")
            AudioFormat = autoclass("android.media.AudioFormat")
            AudioSource = autoclass("android.media.MediaRecorder$AudioSource")
            STATE_INITIALIZED = AudioRecord.STATE_INITIALIZED

            ch = AudioFormat.CHANNEL_IN_MONO
            enc = AudioFormat.ENCODING_PCM_16BIT
            rec = None
            sr = 44100
            # 某些裝置不支援 44100，依序降級嘗試
            for try_sr in (44100, 32000, 22050, 16000, 11025):
                min_buf = AudioRecord.getMinBufferSize(try_sr, ch, enc)
                if min_buf <= 0:
                    continue
                candidate = AudioRecord(AudioSource.MIC, try_sr, ch, enc, min_buf)
                if candidate.getState() == STATE_INITIALIZED:
                    rec = candidate
                    sr = try_sr
                    break
                candidate.release()
            if rec is None:
                self.on_state("錄音初始化失敗：麥克風不支援常用採樣率")
                return False

            rec.startRecording()
            self._rec = rec
            self._path = path
            self._sr = sr
            self.recording = True
            self._start = time.time()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            self.on_state("錄音中…")
            return True
        except Exception as e:
            self.on_state("錄音啟動失敗:" + str(e))
            return False

    def _loop(self):
        chunks = []
        buf = bytearray(2048)
        try:
            while self.recording and self._rec is not None:
                n = self._rec.read(buf, 0, len(buf))
                if n > 0:
                    chunks.append(bytes(buf[:n]))
        except Exception as e:
            print("錄音讀取錯誤:", e)
        finally:
            if self._rec:
                try:
                    self._rec.stop()
                    self._rec.release()
                except Exception:
                    pass
                self._rec = None
            self._write_wav(chunks)

    def _write_wav(self, chunks):
        if not chunks:
            self.on_state("沒有錄到聲音")
            return
        try:
            with wave.open(self._path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self._sr)
                w.writeframes(b"".join(chunks))
            self.on_state("錄音完成")
        except Exception as e:
            self.on_state("寫入 WAV 失敗:" + str(e))

    def stop(self):
        if not self.recording:
            return None
        self.recording = False
        # 等待背景執行緒結束並寫完 WAV，再回傳路徑
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        return self._path


# ============================================================
# 4. 定時層：睡眠定時器
# ============================================================
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


# ============================================================
# 5. 介面層
# ============================================================
KV = r"""
#:import dp kivy.metrics.dp

<InkRadio>:
    ScrollView:
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(12)
            spacing: dp(10)

            # 頂部狀態列
            BoxLayout:
                size_hint_y: None
                height: dp(60)
                orientation: 'vertical'
                spacing: dp(2)
                Label:
                    id: status_label
                    text: '● 待機'
                    color: app.GOLD
                    font_size: dp(16)
                    halign: 'left'
                    text_size: self.width, None
                    size_hint_y: 0.55
                Label:
                    id: now_label
                    text: '目前：—'
                    color: app.CINNABAR
                    font_size: dp(14)
                    halign: 'left'
                    text_size: self.width, None
                    size_hint_y: 0.45

            # 新增電台表單
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(6)
                TextInput:
                    id: name_input
                    hint_text: '電台名稱'
                    hint_text_color: app.GOLD
                    foreground_color: app.GOLD
                    background_color: (0.1, 0.1, 0.1, 1)
                    font_name: 'NotoSansCJK'
                    font_size: dp(14)
                    multiline: False
                TextInput:
                    id: url_input
                    hint_text: '串流網址 .m3u8 / .mp3'
                    hint_text_color: app.GOLD
                    foreground_color: app.GOLD
                    background_color: (0.1, 0.1, 0.1, 1)
                    font_name: 'NotoSansCJK'
                    font_size: dp(13)
                    multiline: False
                Button:
                    id: add_btn
                    text: '典藏'
                    color: app.GOLD
                    size_hint_x: 0.28
                    on_press: root.add_station()

            # 電台典藏清單
            Label:
                text: '電台典藏'
                color: app.GOLD
                size_hint_y: None
                height: dp(24)
                halign: 'left'
                text_size: self.width, None
            ScrollView:
                size_hint_y: None
                height: dp(150)
                GridLayout:
                    id: station_list
                    cols: 1
                    spacing: dp(6)
                    size_hint_y: None
                    height: self.minimum_height

            # 均衡器 EQ
            Label:
                text: '均衡器 (EQ)'
                color: app.GOLD
                size_hint_y: None
                height: dp(24)
                halign: 'left'
                text_size: self.width, None
            BoxLayout:
                id: eq_box
                size_hint_y: None
                height: dp(90)
                spacing: dp(6)
                padding: dp(6)
                canvas.before:
                    Color:
                        rgba: 0.15, 0.15, 0.15, 1
                    Rectangle:
                        pos: self.pos
                        size: self.size
                # 動態填入頻段滑桿

            # 錄音
            Label:
                text: '錄音 (麥克風)'
                color: app.GOLD
                size_hint_y: None
                height: dp(24)
                halign: 'left'
                text_size: self.width, None
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(8)
                Button:
                    id: rec_btn
                    text: '開始錄音'
                    color: app.GOLD
                    on_press: root.toggle_record()
                Label:
                    id: rec_timer
                    text: '00:00'
                    color: app.CINNABAR
                    size_hint_x: 0.3
            ScrollView:
                size_hint_y: None
                height: dp(110)
                GridLayout:
                    id: rec_list
                    cols: 1
                    spacing: dp(4)
                    size_hint_y: None
                    height: self.minimum_height

            # 播放控制
            BoxLayout:
                size_hint_y: None
                height: dp(46)
                spacing: dp(8)
                Button:
                    id: play_btn
                    text: '播放 / 暫停'
                    color: app.GOLD
                    on_press: root.toggle_play()
                Button:
                    id: mute_btn
                    text: '靜音'
                    color: app.GOLD
                    size_hint_x: 0.4
                    on_press: root.toggle_mute()

            # 音量
            BoxLayout:
                size_hint_y: None
                height: dp(36)
                spacing: dp(8)
                Label:
                    text: '音量'
                    size_hint_x: 0.18
                    color: app.GOLD
                Slider:
                    id: volume
                    min: 0
                    max: 100
                    value: 80
                    on_value: root.on_volume(self.value)

            # 睡眠定時
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(8)
                Spinner:
                    id: sleep_spin
                    text: '睡眠定時'
                    color: app.GOLD
                    values: ['15 分鐘', '30 分鐘', '60 分鐘']
                    size_hint_x: 0.5
                Button:
                    id: sleep_btn
                    text: '設定'
                    color: app.GOLD
                    on_press: root.set_sleep()
                Label:
                    id: sleep_label
                    text: ''
                    color: app.CINNABAR
                    size_hint_x: 0.35

            # 開機自動播放
            BoxLayout:
                size_hint_y: None
                height: dp(36)
                spacing: dp(8)
                Button:
                    id: boot_toggle_btn
                    text: '□'
                    color: app.GOLD
                    size_hint_x: 0.12
                    on_press: root.toggle_boot()
                Label:
                    text: '開機自動播放（預設頻道）'
                    color: app.GOLD
                    size_hint_x: 0.88

            # 備份 / 匯入
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(8)
                Button:
                    text: '匯出備份'
                    color: app.GOLD
                    on_press: root.export_stations()
                Button:
                    text: '匯入備份'
                    color: app.GOLD
                    on_press: root.import_stations()
"""


class InkRadio(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = StationStore()
        self.audio = AudioEngine()
        self.recorder = Recorder(self._on_rec_state)
        self.timer = SleepTimer(self._on_sleep_tick, self._on_sleep_end)

        self.current_id = None
        self.prefs = self._load_prefs()
        self.recordings = self._load_recordings()

        self.audio.on_state(self._on_audio_state)
        self.render_stations()
        self.render_recordings()
        self._eq_built = False
        self._build_eq_ui()
        self.ids.boot_toggle_btn.text = '■' if self.prefs.get("autoplay") else '□'
        self._update_sleep_label()
        # 開機自動播放
        if self.prefs.get("autoplay"):
            Clock.schedule_once(lambda dt: self._autoplay(), 3)

    # ---------- 偏好 ----------
    def _prefs_path(self):
        try:
            base = App.get_running_app().user_data_dir
        except Exception:
            base = os.getcwd()
        return os.path.join(base, "prefs.json")

    def _load_prefs(self):
        p = self._prefs_path()
        if os.path.exists(p):
            try:
                return json.load(open(p, "r", encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_prefs(self):
        try:
            json.dump(self.prefs, open(self._prefs_path(), "w", encoding="utf-8"))
        except Exception:
            pass

    def toggle_boot(self):
        active = not self.prefs.get("autoplay", False)
        self.prefs["autoplay"] = active
        self._save_prefs()
        self.ids.boot_toggle_btn.text = '■' if active else '□'
        self.toast("開機自動播放：" + ("開啟" if active else "關閉"))

    def _autoplay(self):
        if self.current_id:
            return
        preset = next((s for s in self.store.stations if s.get("preset")), None)
        if preset:
            self.play_station(preset["id"])

    # ---------- 電台清單 ----------
    def render_stations(self):
        grid = self.ids.station_list
        grid.clear_widgets()
        if not self.store.stations:
            grid.add_widget(Label(text="尚無典藏電台",
                                  color=App.get_running_app().GOLD,
                                  size_hint_y=None, height=40))
            return
        for s in self.store.stations:
            row = BoxLayout(size_hint_y=None, height=44, spacing=8, padding=[6, 0])
            if s["id"] == self.current_id:
                from kivy.graphics import Color, Rectangle
                with row.canvas.before:
                    Color(0.761, 0.227, 0.169, 0.12)
                    Rectangle(pos=row.pos, size=row.size)
                row.bind(pos=lambda w, p: self._refresh_rect(w),
                         size=lambda w, sz: self._refresh_rect(w))
            gold = App.get_running_app().GOLD
            name = Label(text=s["name"], color=gold,
                         halign="left", text_size=(self.width, None),
                         size_hint_x=0.55)
            play = Button(text="播放", color=gold, size_hint_x=0.22)
            play.bind(on_press=lambda inst, sid=s["id"]: self.play_station(sid))
            row.add_widget(name)
            row.add_widget(play)
            if not s.get("preset"):
                delete = Button(text="刪除", color=gold, size_hint_x=0.22)
                delete.bind(on_press=lambda inst, sid=s["id"]: self.delete_station(sid))
                row.add_widget(delete)
            grid.add_widget(row)

    def _refresh_rect(self, widget):
        widget.canvas.before.clear()
        from kivy.graphics import Color, Rectangle
        with widget.canvas.before:
            Color(0.761, 0.227, 0.169, 0.12)
            Rectangle(pos=widget.pos, size=widget.size)

    def add_station(self):
        ok, msg = self.store.add(self.ids.name_input.text, self.ids.url_input.text)
        self.toast(msg)
        if ok:
            self.ids.name_input.text = ""
            self.ids.url_input.text = ""
            self.render_stations()

    def delete_station(self, sid):
        if self.store.remove(sid):
            if self.current_id == sid:
                self.current_id = None
                self.audio.pause()
                self.ids.now_label.text = "目前：—"
            self.render_stations()

    def play_station(self, sid):
        s = self.store.find(sid)
        if not s:
            return
        self.current_id = sid
        self.ids.now_label.text = "目前：" + s["name"]
        self.audio.play_url(s["url"])
        self.render_stations()
        # 主動觸發 EQ 初始化（防止狀態回呼遺漏）
        self._eq_built = False
        self._ensure_eq_sliders()

    # ---------- 播放控制 ----------
    def toggle_play(self):
        if not self.current_id:
            self.toast("請先選擇電台")
            return
        self.audio.toggle()
        # 若開始播放，主動觸發 EQ 初始化
        if self.audio.playing:
            self._eq_built = False
            self._ensure_eq_sliders()

    def on_volume(self, value):
        self.audio.set_volume(value / 100.0)

    def toggle_mute(self):
        if self.audio.muted:
            self.audio.set_muted(False)
            self.ids.mute_btn.text = "靜音"
        else:
            self.audio.set_muted(True)
            self.ids.mute_btn.text = "取消靜音"

    # ---------- 均衡器 ----------
    def _build_eq_ui(self):
        box = self.ids.eq_box
        box.clear_widgets()
        gold = App.get_running_app().GOLD
        if not self.audio._use_native:
            box.add_widget(Label(text="均衡器僅限安卓",
                                 color=gold, font_size=14,
                                 halign="center", valign="middle",
                                 text_size=(box.width, box.height)))
            self._eq_built = True
            return
        # 先放一個佔位，等待播放後取得頻段資訊再填滑桿
        self._eq_built = False
        box.add_widget(Label(text="請先選擇電台並播放，EQ 將自動啟用 (v4)",
                             color=gold, font_size=14,
                             halign="center", valign="middle",
                             text_size=(box.width, box.height)))

    def _ensure_eq_sliders(self, retry=0):
        # 已建立完成就不再動
        if getattr(self, "_eq_built", False):
            return
        # 外部並發呼叫保護：若已有初始化隊列在跑，且本次不是被 schedule 進來的，則跳過
        if retry == 0 and getattr(self, "_eq_initializing", False):
            return

        if retry == 0:
            self._eq_initializing = True

        box = self.ids.eq_box
        gold = App.get_running_app().GOLD
        try:
            if not self.audio.eq_available():
                if retry < 10:
                    # 顯示正在嘗試，讓用戶知道沒有當掉
                    box.clear_widgets()
                    box.add_widget(Label(text="EQ 初始化中… (%d/10)" % (retry + 1),
                                         color=gold, font_size=13,
                                         halign="center", valign="middle",
                                         text_size=(box.width, box.height)))
                    # 給 _setup_eq 延遲初始化一點時間，稍後再試
                    Clock.schedule_once(
                        lambda dt, r=retry: self._ensure_eq_sliders(r + 1), 0.3)
                    return
                # 重試結束仍失敗，標記完成並顯示錯誤
                self._eq_built = True
                self._eq_initializing = False
                err = getattr(self.audio, "_eq_error", None) or "本裝置無法啟用均衡器"
                box.clear_widgets()
                box.add_widget(Label(text=err,
                                     color=gold, font_size=13,
                                     halign="center", valign="middle",
                                     text_size=(box.width, box.height)))
                return
            # 成功取得 EQ
            self._eq_built = True
            self._eq_initializing = False
            box.clear_widgets()
            lo, hi = self.audio.eq_range()
            count = self.audio.eq_band_count()
            if count <= 0:
                box.add_widget(Label(text="EQ 回傳 0 個頻段",
                                     color=gold, font_size=13,
                                     halign="center", valign="middle",
                                     text_size=(box.width, box.height)))
                return
            for b in range(count):
                col = BoxLayout(orientation="vertical", spacing=2)
                cf = self.audio.eq_band_center(b)
                col.add_widget(Label(text="%dHz" % cf, font_size=11,
                                     color=gold,
                                     size_hint_y=0.35))
                sl = Slider(min=lo, max=hi, value=0, orientation="vertical",
                            size_hint_y=0.45, value_track=True,
                            value_track_color=gold,
                            cursor_color=gold,
                            background_color=(0.3, 0.3, 0.3, 1))
                sl.bind(value=lambda v, band=b: self.audio.set_eq_band(band, v.value))
                col.add_widget(sl)
                box.add_widget(col)
            reset = Button(text="重置", color=gold, size_hint_x=0.12)
            reset.bind(on_press=lambda inst: self.audio.reset_eq())
            box.add_widget(reset)
        except Exception as e:
            self._eq_built = True
            self._eq_initializing = False
            box.clear_widgets()
            box.add_widget(Label(text="EQ 載入失敗: " + str(e),
                                 color=gold, font_size=12,
                                 halign="center", valign="middle",
                                 text_size=(box.width, box.height)))

    # ---------- 錄音 ----------
    def request_record_permission(self, on_granted):
        """Android 6.0+ 需要動態請求 RECORD_AUDIO 權限。"""
        if platform != "android":
            on_granted()
            return
        try:
            from android.permissions import (
                request_permissions, Permission, check_permission
            )
            if check_permission(Permission.RECORD_AUDIO):
                on_granted()
            else:
                request_permissions(
                    [Permission.RECORD_AUDIO],
                    lambda perms, grants: (
                        on_granted() if grants and grants[0]
                        else self._on_rec_state("需要錄音權限")
                    ),
                )
        except Exception as e:
            self._on_rec_state("權限檢查失敗:" + str(e))

    def toggle_record(self):
        # 防止按鈕連點導致開始/停止錯亂
        if getattr(self, "_rec_toggling", False):
            return
        self._rec_toggling = True

        def _do_toggle():
            try:
                if self.recorder.is_recording():
                    path = self.recorder.stop()
                    self.ids.rec_btn.text = "開始錄音"
                    if path and os.path.exists(path):
                        self.recordings.append({
                            "name": "錄音_%s" % time.strftime("%m%d_%H%M"),
                            "path": path,
                        })
                        self._save_recordings()
                        self.render_recordings()
                else:
                    rec_dir = os.path.join(self.store.base, "recordings")
                    os.makedirs(rec_dir, exist_ok=True)
                    path = os.path.join(rec_dir, "rec_%s.wav" % int(time.time()))
                    if self.recorder.start(path):
                        self.ids.rec_btn.text = "停止錄音"
                        self._rec_timer_evt = Clock.schedule_interval(
                            self._update_rec_timer, 1)
                    else:
                        self.ids.rec_btn.text = "開始錄音"
            finally:
                self._rec_toggling = False

        self.ids.rec_btn.text = "授權中…"
        self.request_record_permission(_do_toggle)

    def _update_rec_timer(self, dt):
        s = self.recorder.elapsed()
        self.ids.rec_timer.text = "%02d:%02d" % divmod(s, 60)

    def _on_rec_state(self, msg):
        if msg == "錄音完成" and hasattr(self, "_rec_timer_evt"):
            self._rec_timer_evt.cancel()
            self.ids.rec_timer.text = "00:00"
        if "失敗" in msg or "僅限" in msg:
            self.ids.rec_btn.text = "開始錄音"
        self.toast(msg)

    def _rec_path(self):
        return os.path.join(self.store.base, "recordings.json")

    def _load_recordings(self):
        p = self._rec_path()
        if os.path.exists(p):
            try:
                return json.load(open(p, "r", encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_recordings(self):
        try:
            json.dump(self.recordings, open(self._rec_path(), "w", encoding="utf-8"))
        except Exception:
            pass

    def render_recordings(self):
        grid = self.ids.rec_list
        grid.clear_widgets()
        gold = App.get_running_app().GOLD
        if not self.recordings:
            grid.add_widget(Label(text="尚無錄音",
                                  color=gold,
                                  size_hint_y=None, height=36))
            return
        for idx, r in enumerate(self.recordings):
            row = BoxLayout(size_hint_y=None, height=36, spacing=6, padding=[4, 0])
            name = Label(text=r["name"], color=gold,
                         halign="left", size_hint_x=0.5)
            play = Button(text="播放", color=gold, size_hint_x=0.25)
            play.bind(on_press=lambda inst, p=r["path"]: self._play_rec(p))
            delete = Button(text="刪除", color=gold, size_hint_x=0.25)
            delete.bind(on_press=lambda inst, i=idx: self._del_rec(i))
            row.add_widget(name)
            row.add_widget(play)
            row.add_widget(delete)
            grid.add_widget(row)

    def _play_rec(self, path):
        if platform == "android":
            # 直接以原生 MediaPlayer 播放 WAV
            try:
                from jnius import autoclass
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                mp = autoclass("android.media.MediaPlayer")()
                mp.setDataSource(PythonActivity.mActivity, Uri.parse("file://" + path))
                mp.prepare()
                mp.start()
                return
            except Exception as e:
                self.toast("播放失敗:" + str(e))
        from kivy.core.audio import SoundLoader
        s = SoundLoader.load(path)
        if s:
            s.play()

    def _del_rec(self, idx):
        try:
            os.remove(self.recordings[idx]["path"])
        except Exception:
            pass
        del self.recordings[idx]
        self._save_recordings()
        self.render_recordings()

    # ---------- 睡眠定時 ----------
    def set_sleep(self):
        txt = self.ids.sleep_spin.text
        minutes = {"15 分鐘": 15, "30 分鐘": 30, "60 分鐘": 60}.get(txt)
        if not minutes:
            self.toast("請選擇定時長度")
            return
        self.timer.start(minutes)
        self.ids.sleep_btn.text = "取消定時"
        self.ids.sleep_btn.unbind(on_press=self.set_sleep)
        self.ids.sleep_btn.bind(on_press=self.cancel_sleep)
        self._update_sleep_label()

    def cancel_sleep(self):
        self.timer.cancel()
        self.ids.sleep_btn.text = "設定"
        self.ids.sleep_btn.unbind(on_press=self.cancel_sleep)
        self.ids.sleep_btn.bind(on_press=self.set_sleep)
        self._update_sleep_label()

    def _on_sleep_tick(self, remaining):
        self._update_sleep_label()

    def _on_sleep_end(self):
        self.audio.pause()
        self.toast("睡眠定時結束，已暫停")
        self.ids.sleep_btn.text = "設定"
        self.ids.sleep_btn.unbind(on_press=self.cancel_sleep)
        self.ids.sleep_btn.bind(on_press=self.set_sleep)
        self._update_sleep_label()

    def _update_sleep_label(self):
        r = self.timer.remaining
        self.ids.sleep_label.text = "" if r <= 0 else "剩 %02d:%02d" % divmod(r, 60)

    # ---------- 備份 / 匯入 ----------
    def export_stations(self):
        path = os.path.join(self.store.base, "stations_backup.json")
        self.store.export_to(path)
        self.toast("已匯出：" + path)

    def import_stations(self):
        from kivy.uix.filechooser import FileChooserListView
        from kivy.uix.popup import Popup
        fc = FileChooserListView(filters=["*.json"])
        box = BoxLayout(orientation="vertical")
        box.add_widget(fc)
        done = Button(text="匯入選取檔案", size_hint_y=0.15)
        box.add_widget(done)
        popup = Popup(title="選擇備份 JSON", content=box, size_hint=(0.9, 0.9))
        def do_import(inst):
            if fc.selection:
                added, msg = self.store.import_from(fc.selection[0])
                self.toast(msg)
                self.render_stations()
            popup.dismiss()
        done.bind(on_press=do_import)
        popup.open()

    # ---------- 狀態回呼 ----------
    def _on_audio_state(self, state):
        if state == "playing":
            self.ids.status_label.text = "● 播放中"
            if not getattr(self, "_eq_built", False):
                self._ensure_eq_sliders()
        elif state == "paused":
            self.ids.status_label.text = "● 已暫停"
        elif state == "error":
            self.ids.status_label.text = "● 播放失敗（網址或跨域）"
            self.toast("無法播放此電台")

    # ---------- 輔助 ----------
    def toast(self, msg):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        pop = Popup(title="提示", content=Label(text=msg), size_hint=(0.7, 0.3))
        pop.open()
        Clock.schedule_once(lambda dt: pop.dismiss(), 1.8)


class InkRadioApp(App):
    PAPER = (0.961, 0.949, 0.922, 1)
    CARD = (0.918, 0.898, 0.851, 1)
    CINNABAR = (0.761, 0.227, 0.169, 1)
    INK = (0.169, 0.169, 0.169, 1)
    GOLD = (1.0, 0.84, 0.0, 1)   # 黑底上的黃色標籤文字

    def build(self):
        Builder.load_string(KV)
        return InkRadio()


if __name__ == "__main__":
    InkRadioApp().run()
