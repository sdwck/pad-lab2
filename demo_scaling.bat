@echo off
title Kubernetes Scaling & Self-Healing Defense Demonstration
cd /d "%~dp0"

echo =========================================================================
echo    CloudMart Kubernetes Defense Demo: Scaling & Self-Healing
echo              PAD Lab 3 - Docker & Kubernetes - FCIM UTM
echo =========================================================================
echo.

where kubectl >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] kubectl is not in PATH.
    pause
    exit /b 1
)

echo [STEP 1] Checking current replica count for order-service...
kubectl get deployment order-service -n pad
echo.
pause

echo [STEP 2] Horizontal Pod Autoscaling Demonstration:
echo Scaling order-service from 2 to 4 replicas...
echo Command: kubectl scale deployment order-service --replicas=4 -n pad
kubectl scale deployment order-service --replicas=4 -n pad
echo.
echo Waiting 5 seconds for replica spin-up...
timeout /t 5 /nobreak >nul
kubectl get pods -l app=order-service -n pad -o wide
echo.
pause

echo [STEP 3] Self-Healing and Pod Fault-Tolerance Demonstration:
echo Finding one order-service pod to terminate...
for /f "tokens=1" %%i in ('kubectl get pods -l app^=order-service -n pad --no-headers ^| findstr "order-service"') do (
    set POD_TO_KILL=%%i
    goto :kill_pod
)

:kill_pod
echo Terminating pod: %POD_TO_KILL%
echo Command: kubectl delete pod %POD_TO_KILL% -n pad --grace-period=1
kubectl delete pod %POD_TO_KILL% -n pad --grace-period=1
echo.
echo Watching Kubernetes controller immediately detect failure and provision healthy replacement...
timeout /t 3 /nobreak >nul
kubectl get pods -l app=order-service -n pad -o wide
echo.
pause

echo [STEP 4] Reverting replica count back to baseline (2 replicas)...
kubectl scale deployment order-service --replicas=2 -n pad
echo.
kubectl get deployment order-service -n pad
echo.
echo =========================================================================
echo [SUCCESS] Defense demonstration complete.
echo =========================================================================
pause
