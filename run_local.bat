@echo off
title CloudMart 12 Microservices Platform (Local)
cd /d "%~dp0"

echo ========================================================
echo    CloudMart Distributed Microservices Platform
echo              PAD Lab 2 - FCIM UTM
echo ========================================================

if exist ".venv\Scripts\python.exe" (
    echo Starting all 12 microservices + API Gateway...
    .venv\Scripts\python.exe dev_runner.py
) else (
    echo [ERROR] Virtual environment not found. Run: uv venv and uv pip install -r requirements.txt
    pause
)
