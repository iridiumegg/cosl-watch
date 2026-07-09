@echo off
REM ============================================================
REM  Registers a Windows Scheduled Task:
REM    Name : COSL_Watch
REM    When : Every Monday at 8:00 AM
REM    Runs : run_cosl_watch.bat  (in this folder)
REM  Run this file ONCE (right-click > Run as administrator).
REM ============================================================
set SCRIPT_DIR=%~dp0

schtasks /Create ^
 /TN "COSL_Watch" ^
 /TR "\"%SCRIPT_DIR%run_cosl_watch.bat\"" ^
 /SC WEEKLY ^
 /D MON ^
 /ST 08:00 ^
 /RL LIMITED ^
 /F

echo.
echo Done. To verify:   schtasks /Query /TN "COSL_Watch"
echo To run it now:      schtasks /Run   /TN "COSL_Watch"
echo To remove it:       schtasks /Delete /TN "COSL_Watch" /F
pause
