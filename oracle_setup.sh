#!/bin/bash
# 水墨電台 - Oracle Cloud (Ubuntu) 一鍵安裝 Docker 並打包 APK
# 用法：把專案放到 ~/inkradio 後，執行  bash oracle_setup.sh
set -e

sudo apt-get update -y
sudo apt-get install -y git curl
curl -fsSL https://get.docker.com | sudo sh

cd ~/inkradio
echo "開始打包（首次下載 Android SDK/NDK，約 15~30 分鐘）..."
sudo docker run --rm -v "$PWD":/home/user/host -w /home/user/host kivy/buildozer:latest bash -c "buildozer android debug"
echo "完成！APK 位於 ~/inkradio/bin/"
