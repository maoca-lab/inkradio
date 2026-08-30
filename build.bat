@echo off
REM 水墨電台 - Windows 一鍵 Docker 打包 APK
REM 前置條件：已安裝並「啟動」Docker Desktop
cd /d "%~dp0"

docker --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Docker。請先安裝 Docker Desktop：
    echo https://www.docker.com/products/docker-desktop/
    echo 安裝完成後，請先「啟動」Docker Desktop（工作列出現鯨魚圖示），再雙擊本檔。
    pause
    exit /b 1
)

echo 開始打包（首次會下載鏡像與 Android SDK，約 20~40 分鐘，請耐心等候）...
docker run --rm -v "%cd%":/home/user/host -w /home/user/host kivy/buildozer:latest bash -c "buildozer android debug"
echo.
echo 若成功，APK 會出現在 bin\ 資料夾中。
pause
