[app]

# (str) Title of your application
title = 水墨電台

# (str) Package name
package.name = inkradio

# (str) Package domain (needed for android/ios packaging)
package.domain = org.inkradio

# (str) Source to include (let gradle handle the android entry point)
source.include_exts = py,png,jpg,kv,json,atlas,ttf,ttc,otf

# (list) Source files to include (let include_exts decide if empty)
source.include_patterns = *

# (list) List of inclusions using pattern matching
source.exclude_patterns = bin,obj,*.pyc,*.pyo,build,dist

# (str) Application versioning (method 1)
version = 1.0

# (str) Supported orientation (one of landscape/portrait/landscape-reverse/portrait-reverse/landscape|portrait)
orientation = portrait

# (list) List of service to declare
# services = Name:Path

# (list) Application requirements
# 安卓上 jnius 由 buildozer 自動提供，不需列在 requirements
# 加入 android 以取得動態權限請求模組 (android.permissions)
requirements = python3,kivy,android

# (str) Custom source folders for requirements
source.dir = .

# (list) Garden requirements
# garden_requirements =

# (str) Presplash of the application
# presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
# icon.filename = %(source.dir)s/data/icon.png

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET, WAKE_LOCK, ACCESS_NETWORK_STATE, RECEIVE_BOOT_COMPLETED, RECORD_AUDIO

# (str) 額外 manifest（開機自播的 receiver 宣告）
android.extra_manifest = extra_manifest.xml

# (list) 額外 Java 原始碼（編譯進 APK）
android.add_java_libs = java/

# (int) Target Android API level (newer NDK needs 24+)
android.api = 31
android.minapi = 21
android.ndk = 25b

# (bool) Auto accept Android SDK licenses in non-interactive CI environment
android.accept_sdk_license = True

# (list) Only build arm64 to save time and reduce failure points in CI
android.archs = arm64-v8a

# (bool) Show build log
log_level = 2

# (str) Path to a custom kivy-requirements recipe (optional)
# kivy.requirements = sdl2_ttf

# (list) Android additional libraries to copy into libs/armeabi
# android.add_libs_armeabi = libs/android/*.so

# (bool) Android logcat filters
# android.logcat_filters = *:S python:D

# (list) Android application meta-data to set (key=value format)
# android.meta_data =

# (list) Android service to declare
# android.services =

[buildozer]

# (int) Log level (0 = silent, 1 = important, 2 = all)
log_level = 2

# (str) Path of the build cache
build_dir = ./.buildozer

# (str) Path to build output (usually ./(target)platform/(type))
bin_dir = ./bin

# (str,bool) Warn if buildozer is run as root
warn_on_root = 0
