@echo off
title CloudMart Kubernetes & Docker Cluster (Compose Mode)
cd /d "%~dp0"

echo =========================================================================
echo    CloudMart Distributed Microservices Platform (Docker Orchestration)
echo              PAD Lab 3 - Docker & Kubernetes - FCIM UTM
echo =========================================================================

echo.
echo [*] Building and launching 12 microservices + Redis + Gateway...
echo.

docker compose up --build

pause
