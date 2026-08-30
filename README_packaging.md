# 水墨電台 · 安卓 APK 打包說明

本說明教你把 `ink_radio_kivy.py` 打包成可在安卓手機安裝的 `APK`。
推薦使用 **Buildozer**（官方工具），並建議在 **Linux / Docker / WSL** 環境執行。

---

## 〇、最快方式：Colab 雲端一鍵打包（推薦新手）

不想在本機裝 SDK/NDK？直接用本專案附好的成品去 Google Colab 編譯：

1. 下載預打包好的 **`inkradio_colab_build.zip`**（已含 `ink_radio_kivy.py`、`buildozer.spec`、`extra_manifest.xml`、`java/`）。
2. 打開 **`colab_build_apk.ipynb`**，從上到下依序執行程式碼格。
3. 跑到「上傳專案 zip」那格時，上傳 `inkradio_colab_build.zip`。
4. 等待 Buildozer 自動下載 SDK/NDK 並編譯（首次約 15–30 分鐘，**建議用 Colab Pro**，免費版容易逾時斷線）。
5. 最後一格會自動下載 `bin/*.apk`，傳到手機安裝即可。

> 若想改 App 程式碼，解壓 zip 改完後重新壓回 zip 再上傳即可；其餘步驟不變。

---

## 〇之一、最穩方案：Windows 電腦 + Docker（推薦新手）

若你有一台 **Windows 電腦/筆電**，用 Docker 在本機打包最穩，不會像免費 Colab 那樣斷線。安卓平板**不能**跑 Docker，它只負責最後安裝 APK。

### 事前準備（一次性）
1. 下載並安裝 **Docker Desktop**：https://www.docker.com/products/docker-desktop/
2. 安裝時全部按「下一步」即可（會自動幫你啟用 WSL2）。
3. 安裝完**務必啟動 Docker Desktop**（工作列出現一隻鯨魚圖示，且圖示穩定不轉圈），再繼續。

### 打包步驟
1. 把專案 zip 解壓到電腦任意資料夾（例如 `D:\inkradio`）。
2. 確認資料夾內有 `build.bat`、`ink_radio_kivy.py`、`buildozer.spec`、`extra_manifest.xml`、`java\`。
3. **雙擊 `build.bat`**。
4. 首次會自動下載 Docker 鏡像與 Android SDK/NDK（約 20~40 分鐘，只看這一次；之後重編只要幾分鐘）。
5. 完成後 APK 在 `bin\` 資料夾，副檔名 `.apk`。

### 把 APK 裝到安卓平板
- 用 USB 傳、或用微信/網盤把 `.apk` 傳到平板。
- 平板開啟「設定 → 安全性 → 允許未知來源」，點開 APK 即可安裝。

> 小提醒：打包會吃記憶體，電腦最好有 8GB 以上（16GB 更順）；磁碟預留約 10GB。

---

## 一、準備環境（只在打包機上需要）

### 方式 A：Linux 原生（Ubuntu/Debian）
```bash
sudo apt update
sudo apt install -y python3-pip python3-setuptools git zip unzip \
    openjdk-17-jdk autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev \
    ffmpeg libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libgstreamer1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad

pip3 install --user buildozer
```

### 方式 B：Docker（最省事，跨平台通用）
```bash
docker run --rm -v "$PWD":/home/user/host -w /home/user/host \
    kivy/buildozer:latest bash -c "buildozer android debug"
```
> 把本目錄掛載進容器即可，容器內已含全部依賴。

---

## 二、執行打包

在含 `ink_radio_kivy.py` 與 `buildozer.spec` 的目錄執行：

```bash
# 首次會自動下載 Android SDK/NDK，請保持網路暢通（約 10~20 分鐘）
buildozer android debug
```

完成後產出：
```
./bin/inkradio-1.0-armeabi-v7a-debug.apk
```

（如需 64 位元 `arm64-v8a`，可在 `buildozer.spec` 加：
`android.archs = arm64-v8a`）

---

## 三、安裝到手機

1. 手機開啟「設定 → 關於手機 → 連點版本號」啟用開發者模式。
2. 開啟「USB 偵錯」，用資料線連上電腦。
3. 電腦執行：
   ```bash
   buildozer android deploy run
   ```
   或直接把 `.apk` 傳到手機，點擊安裝（需允許「未知來源」）。

---

## 四、功能對應與注意事項

| 功能 | 實作 | 備註 |
|------|------|------|
| 播放 / 暫停 | `AudioEngine` | 安卓走原生 `MediaPlayer`，桌面走 Kivy `SoundLoader` |
| .m3u8 HLS | 原生 `MediaPlayer` | **只有打包進 APK 後才支援**；桌面測試 .m3u8 可能無聲 |
| .mp3 串流 | 雙平台皆支援 | — |
| 音量 / 靜音 | `AudioEngine.set_volume / set_muted` | — |
| 電台典藏 CRUD | `StationStore` | 存於 `stations.json`（App 私有目錄） |
| 自動去重 | `StationStore.add` | 名稱或網址重複即略過 |
| 匯出 / 匯入 JSON | `export_to / import_from` | 匯入自動清理重複 |
| 睡眠定時 | `SleepTimer` | 15/30/60 分倒數，歸零自動暫停 |
| 均衡器 EQ | 原生 `android.media.audiofx.Equalizer` | 僅安卓生效；桌面無 EQ |
| 麥克風錄音 | `AudioRecord` → WAV | 存於 `recordings/`（安卓僅能錄麥克風，無法錄系統內部聲音）|
| 開機自動播放 | `BootReceiver` + `prefs.json` | 需 `RECEIVE_BOOT_COMPLETED` 權限；於設定開啟 |

**權限說明**：`INTERNET` 用於連網收聽；`WAKE_LOCK` 避免睡眠期間被系統喚醒中斷；`ACCESS_NETWORK_STATE` 偵測網路狀態；`RECEIVE_BOOT_COMPLETED` 用於開機自動播放（需在 App 設定內開啟）。

**桌面預覽**：在電腦上 `python ink_radio_kivy.py` 可測試 UI 與 .mp3 播放（需 `pip install kivy`）。HLS 直播建議直接在安卓 APK 中驗證。

---

## 五、簽名發佈（上架 / 正式安裝）

Debug APK 僅供測試；要正式分發或上架 Google Play，需自建簽名憑證（keystore）。

### 1. 產生簽名金鑰
```bash
keytool -genkey -v \
    -keystore my-release-key.keystore \
    -alias inkradio \
    -keyalg RSA -keysize 2048 -validity 10000
```
過程會詢問密碼與基本資訊，請牢記密碼（遺失即無法更新同一 App）。

### 2. 在 buildozer.spec 填入簽名資訊
```ini
# 在 [app] 區段加入：
android.release_keystore = my-release-key.keystore
android.release_keyalias = inkradio
android.release_keystore_password = 你的keystore密碼
android.release_keyalias_password = 你的alias密碼
```

### 3. 產生正式（簽名）版本
```bash
buildozer android release
```
- 新版本 Buildozer 預設產出 **AAB**（Android App Bundle）：`./bin/inkradio-1.0-armeabi-v7a-release.aab`，直接上傳 Google Play 即可。
- 若需 **簽名 APK**（側載安裝用），可額外執行：
  ```bash
  # 用 build-tools 的 apksigner 對 aligned apk 簽名
  zipalign -p 4 bin/inkradio-*-unsigned.apk bin/inkradio-aligned.apk
  apksigner sign --ks my-release-key.keystore --ks-key-alias inkradio bin/inkradio-aligned.apk
  ```

### 4. 版本號遞增
每次上架更新請把 `buildozer.spec` 的 `version = 1.0` 調高（如 `1.1`），否則 Play 商店會拒絕同名舊版。

**安全提醒**：`my-release-key.keystore` 與密碼請離線妥善備份，切勿提交進版本庫（可加入 `.gitignore`）。
