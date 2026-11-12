# Kubernetes Deployment and Verification Guide

## 1. Clone Repository
```bash
git clone https://github.com/sdwck/pad-lab2.git
cd pad-lab2
```

## 2. Build Container Images
Build local base images for backend microservices and API gateway:
```bash
docker compose build
```

## 3. Deploy Stack to Kubernetes
Apply declarative manifests within the `pad` namespace:
```bash
kubectl apply -f k8s/
```

## 4. Verify Cluster Health
Verify all pods, deployments, and services:
```bash
kubectl get pods -n pad -o wide
kubectl get deployments -n pad
kubectl get svc -n pad
```

## 5. Horizontal Pod Autoscaling Verification
Scale the order management microservice from 2 to 4 instances:
```bash
kubectl scale deployment order-service --replicas=4 -n pad
kubectl get pods -l app=order-service -n pad -o wide
```

## 6. Fault Tolerance and Self-Healing Verification
Simulate pod termination to observe automated reconciliation by the ReplicaSet controller:
```bash
# Terminate any running order-service pod instance
kubectl delete pod <pod-name> -n pad

# Observe immediate replacement provisioning (Zero Downtime)
kubectl get pods -l app=order-service -n pad -o wide
```

## 7. Web UI Access
Forward gateway service traffic to port 80:
```bash
kubectl port-forward svc/gateway-service 80:80 -n pad
```
Access the application dashboard at `http://localhost`.
