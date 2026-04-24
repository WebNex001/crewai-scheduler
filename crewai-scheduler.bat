@echo off
chcp 65001 >nul
REM CrewAI Scheduler - OpenClaw Skill Wrapper

cd /d "%~dp0"
python __main__.py %*
