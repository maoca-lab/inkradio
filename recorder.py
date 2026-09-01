# -*- coding: utf-8 -*-
"""錄音層：安卓麥克風 AudioRecord → 16-bit PCM WAV（平台相關程式集中於 start()）。"""

import os
import time
import threading
import wave
from kivy.utils import platform


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
