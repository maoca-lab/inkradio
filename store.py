# -*- coding: utf-8 -*-
"""資料層：電台典藏庫（純邏輯，不依賴任何平台或 UI）。"""

import os
import json
import uuid
from kivy.app import App


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
