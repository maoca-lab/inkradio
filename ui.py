# -*- coding: utf-8 -*-
"""
介面層（UI）：水墨 UI 與事件綁定。

本層只負責「畫面」與「把使用者操作轉交給邏輯層」，不內含平台 API。
顏色常數來自 constants；邏輯分別來自 store / audio / recorder / timer。
"""

import os
import json
import time

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.gridlayout import GridLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.core.text import LabelBase

from constants import PAPER, CARD, CINNABAR, INK, GOLD
from store import StationStore
from audio import AudioEngine
from recorder import Recorder
from timer import SleepTimer
from android_player import play_recording

# 註冊中文字體，避免中文在 APK 內顯示為方塊
LabelBase.register(name='NotoSansCJK',
                   fn_regular='NotoSansCJK-Regular.ttc')
Label.font_name = 'NotoSansCJK'
Button.font_name = 'NotoSansCJK'


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
            box.add_widget(self._eq_label("均衡器僅限安卓", gold))
            self._eq_built = True
            return
        # 先放一個佔位，等待播放後取得頻段資訊再填滑桿
        self._eq_built = False
        box.add_widget(self._eq_label("請先選擇電台並播放，EQ 將自動啟用 (v7)", gold))

    def _eq_label(self, text, color):
        """產生一個在 eq_box 內可見的置中 Label。"""
        lb = Label(text=text, color=color, font_size=14,
                   halign="center", valign="middle",
                   size_hint_y=None, height=self.ids.eq_box.height)
        # 當 box 高度確定後，自動調整 text_size 以正確換行置中
        def _resize(*args):
            lb.height = self.ids.eq_box.height
            lb.text_size = (self.ids.eq_box.width, self.ids.eq_box.height)
        self.ids.eq_box.bind(height=_resize, width=_resize)
        # 給初始值
        _resize()
        return lb

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
                    box.add_widget(self._eq_label("EQ 初始化中… (%d/10)" % (retry + 1), gold))
                    # 給 _setup_eq 延遲初始化一點時間，稍後再試
                    Clock.schedule_once(
                        lambda dt, r=retry: self._ensure_eq_sliders(r + 1), 0.3)
                    return
                # 重試結束仍失敗，標記完成並顯示錯誤，並提供手動刷新按鈕
                self._eq_built = True
                self._eq_initializing = False
                err = getattr(self.audio, "_eq_error", None) or "本裝置無法啟用均衡器"
                box.clear_widgets()
                box.add_widget(self._eq_label(err, gold))
                return
            # 成功取得 EQ
            self._eq_built = True
            self._eq_initializing = False
            box.clear_widgets()
            lo, hi = self.audio.eq_range()
            count = self.audio.eq_band_count()
            if count <= 0:
                box.add_widget(self._eq_label("EQ 回傳 0 個頻段", gold))
                return
            for b in range(count):
                col = BoxLayout(orientation="vertical", spacing=2)
                cf = self.audio.eq_band_center(b)
                col.add_widget(Label(text="%dHz" % cf, font_size=11,
                                     color=gold,
                                     size_hint_y=0.35))
                sl = Slider(min=lo, max=hi, value=0, orientation="vertical",
                            size_hint_y=0.45, value_track=True,
                            value_track_color=gold)
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
            box.add_widget(self._eq_label("EQ 載入失敗: " + str(e), gold))

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
            # 直接以原生 MediaPlayer 播放 WAV（平台邊界已抽離至 android_player）
            try:
                play_recording(path)
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
    PAPER = PAPER
    CARD = CARD
    CINNABAR = CINNABAR
    INK = INK
    GOLD = GOLD   # 黑底上的黃色標籤文字

    def build(self):
        Builder.load_string(KV)
        return InkRadio()
