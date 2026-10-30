@echo off
title CloudMart 12 Microservices Platform (Docker)
cd /d "%~dp0"

echo ========================================================
echo    Launching 12 Microservices via Docker Compose
echo              PAD Lab 2 - FCIM UTM
echo ========================================================

docker compose up --build
pause
