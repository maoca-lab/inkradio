# -*- coding: utf-8 -*-
"""水墨電台 APK 入口（buildozer 需要根目錄有 main.py）
加了全域異常捕獲：啟動崩潰時會直接顯示錯誤文字，方便排查。"""

import traceback
import kivy
from kivy.app import App
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label


def _show_error(msg):
    class _ErrApp(App):
        def build(self):
            sv = ScrollView()
            lb = Label(text=msg, font_size=12,
                       text_size=(360, None), size_hint_y=None)
            lb.bind(texture_size=lambda *a: setattr(lb, "height", lb.texture_size[1]))
            sv.add_widget(lb)
            return sv
    _ErrApp().run()


try:
    from ink_radio_kivy import InkRadioApp
    InkRadioApp().run()
except Exception as e:
    _show_error("啟動失敗：\n\n" + traceback.format_exc())
