@echo off
REM ============================================================
REM  COSL Watch weekly runner
REM  Edit the two paths below if your Python / folder differ.
REM ============================================================
set PYTHON=python
set SCRIPT_DIR=%~dp0

cd /d "%SCRIPT_DIR%"
"%PYTHON%" "%SCRIPT_DIR%cosl_watch.py" >> "%SCRIPT_DIR%cosl_watch.log" 2>&1
