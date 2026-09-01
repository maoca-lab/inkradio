# -*- coding: utf-8 -*-
"""水墨電台 App 入口：啟動 UI，並在崩潰時把錯誤顯示在螢幕上。"""

import traceback
from kivy.app import App
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label


def _show_error(msg):
    class _ErrApp(App):
        def build(self):
            sv = ScrollView()
            lb = Label(text=msg, font_size=12, text_size=(360, None), size_hint_y=None)
            lb.bind(texture_size=lambda *a: setattr(lb, "height", lb.texture_size[1]))
            sv.add_widget(lb)
            return sv
    _ErrApp().run()


try:
    from ui import InkRadioApp
    InkRadioApp().run()
except Exception as e:
    _show_error("啟動失敗：\n\n" + traceback.format_exc())
