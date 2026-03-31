@echo off
cd /d %~dp0

echo [1/3] 기존 build/dist 정리...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo [2/3] exe 생성...
pyinstaller --noconfirm --onefile --windowed --name ChromeCord --icon=icon.ico main.py

echo [3/3] 완료
pause