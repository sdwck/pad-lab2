@echo off
title CloudMart Kubernetes Deployment
cd /d "%~dp0"

echo =========================================================================
echo    CloudMart Distributed Microservices Platform (Kubernetes Orchestration)
echo              PAD Lab 3 - Docker & Kubernetes - FCIM UTM
echo =========================================================================
echo.

where kubectl >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] kubectl is not in PATH. Please install kubectl or start Minikube/Docker Desktop.
    pause
    exit /b 1
)

echo [*] Applying Kubernetes manifests in namespace: pad...
kubectl apply -f k8s/

echo.
echo [*] Waiting for deployments to become ready...
kubectl rollout status deployment/order-service -n pad --timeout=60s
kubectl rollout status deployment/catalog-service -n pad --timeout=60s

echo.
echo =========================================================================
echo [OK] CLUSTER STATUS IN NAMESPACE: pad
echo =========================================================================
echo.
echo --- PODS ---
kubectl get pods -n pad -o wide
echo.
echo --- DEPLOYMENTS ---
kubectl get deployments -n pad
echo.
echo --- SERVICES ---
kubectl get services -n pad
echo.
echo =========================================================================
echo Web UI NodePort Gateway available at: http://localhost:30080 or port-forward:
echo   kubectl port-forward svc/gateway-service 80:80 -n pad
echo =========================================================================
echo.
pause
