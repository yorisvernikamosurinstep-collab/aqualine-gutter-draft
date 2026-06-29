@echo off
cd /d "%~dp0"

:: สั่งรันระบบ Site Assessment เบื้องหลัง
start /b python -m streamlit run app.py --server.headless true

:: รอระบบเตรียมตัว 5 วินาที
timeout /t 5 /nobreak > nul

:: เปิดหน้าจอ Site Assessment
start chrome.exe --profile-directory="Default" "http://localhost:8502"

exit