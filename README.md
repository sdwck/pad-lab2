# Лабораторная работа №3. Docker и Kubernetes: Контейнеризация и Оркестрация Распределённой Микросервисной Платформы CloudMart

> **Курс:** Проектирование Архитектуры Распределённых Систем (PAD)  
> **Университет:** Технический Университет Молдовы (UTM / FCIM)  
> **Тема:** Контейнеризация микросервисов с помощью Docker и их оркестрация в кластере Kubernetes / Minikube  
> **Проект:** CloudMart — распределённая high-load e-commerce платформа из 12 независимых микросервисов + Redis In-Memory Cache + API Gateway + Reactive SPA Frontend  

---

## 1. Описание проекта

В рамках третьей лабораторной работы выполнена комплексная контейнеризация и оркестрация распределённой системы **CloudMart**, разработанной во второй лабораторной работе.

Система состоит из **12 микросервисов**, распределённого кэша **Redis**, обратного прокси/шлюза **API Gateway** и реактивного веб-клиента **SPA Frontend**. Каждый сервис упакован в отдельный оптимизированный Docker-образ согласно принципам *Least Privilege* (непривилегированный пользователь `appuser`, многослойное кэширование, отсутствие захардкоженных секретов) и развёрнут в изолированном пространстве имён Kubernetes (`namespace: pad`).

### Состав микросервисов кластера

| № | Микросервис | Порт | Роль и Функционал | Тип K8s Service | Replicas | Data Storage / Cache |
|---|---|---|---|---|---|---|
| 1 | `auth-service` | 8001 | Аутентификация, RBAC, выпуск и верификация JWT | ClusterIP | 1 | PersistentVolumeClaim (`/data/auth.json`) |
| 2 | `catalog-service` | 8002 | Управление каталогом товаров, остатками и категориями | ClusterIP | 2 *(HA)* | PersistentVolumeClaim (`/data/catalog.json`) |
| 3 | `search-service` | 8003 | Полнотекстовый поиск, фильтрация и Redis L1 Cache | ClusterIP | 1 | Redis ClusterIP (`redis-service:6379`) |
| 4 | `cart-service` | 8004 | Управление корзинами покупателей и расчёт стоимости | ClusterIP | 1 | PersistentVolumeClaim (`/data/cart.json`) |
| 5 | `order-service` | 8005 | Оформление заказов, транзакционный стейт-машин | ClusterIP | 2 *(HA)* | PersistentVolumeClaim (`/data/orders.json`) |
| 6 | `payment-service` | 8006 | Обработка платежей, Stripe-симуляция, антифрод | ClusterIP | 1 | PersistentVolumeClaim (`/data/payments.json`) |
| 7 | `review-service` | 8007 | Отзывы, звёздные рейтинги, пересчёт средних оценок | ClusterIP | 1 | PersistentVolumeClaim (`/data/reviews.json`) |
| 8 | `recommendation-service` | 8008 | Персональные рекомендации и связки оборудования | ClusterIP | 1 | Stateless (Inter-service REST) |
| 9 | `notification-service` | 8009 | Журнал транзакционных email/SMS оповещений | ClusterIP | 1 | PersistentVolumeClaim (`/data/notifications.json`) |
| 10 | `analytics-service` | 8010 | BI-метрики, GMV, средний чек, конверсия | ClusterIP | 1 | Stateless (REST Aggregator) |
| 11 | `support-service` | 8011 | Система тикетов техподдержки и обращений | ClusterIP | 1 | PersistentVolumeClaim (`/data/support.json`) |
| 12 | `audit-service` | 8012 | Неизменяемый журнал аудита событий безопасности | ClusterIP | 1 | PersistentVolumeClaim (`/data/audit.json`) |
| 13 | `redis-service` | 6379 | In-memory кэш сессий и поисковых запросов | ClusterIP | 1 | In-Memory Key-Value Store |
| 14 | `gateway-service` | 80 | API Gateway, SPA Frontend, K8s Control Plane | NodePort (30080) | 2 *(HA)* | Nginx / Python FastAPI Gateway |

---

## 2. Архитектура системы в Kubernetes

Все сервисы изолированы внутри Kubernetes Namespace `pad`. Взаимодействие между сервисами происходит **исключительно через внутренний DNS кластера (CoreDNS)** без использования `localhost` или прямых IP-адресов.

```text
                                  ИНТЕРНЕТ / БРАУЗЕР
                                         │
                                         ▼
                            ┌────────────────────────┐
                            │ NodePort Service :30080│
                            │   (gateway-service)    │
                            └───────────┬────────────┘
                                        │
                         Kubernetes Namespace: pad
       ┌────────────────────────────────┴────────────────────────────────┐
       │                                                                 │
       │                   ┌─────────────────────────┐                   │
       │                   │  API Gateway & SPA Pods │                   │
       │                   │       (2 Replicas)      │                   │
       │                   └────────────┬────────────┘                   │
       │                                │                                │
       │     CoreDNS Маршрутизация по внутренним ClusterIP именам:       │
       │                                                                 │
       │    ┌──────────────────┬──────────────────┬─────────────────┐    │
       │    ▼                  ▼                  ▼                 ▼    │
       │ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────┐│
       │ │ auth-service │  │catalog-service│ │search-service│  │  cart  ││
       │ │  Port: 8001  │  │  Port: 8002  │  │  Port: 8003  │  │:8004   ││
       │ └──────────────┘  └──────┬───────┘  └──────┬───────┘  └────────┘│
       │                          │                 │                    │
       │                          │ (2 Replicas)    ▼                    │
       │                          │          ┌──────────────┐            │
       │                          │          │redis-service │            │
       │                          │          │  Port: 6379  │            │
       │    ┌─────────────────────┼──────────┴──────────────┤            │
       │    ▼                     ▼                         ▼            │
       │ ┌──────────────┐  ┌──────────────┐          ┌──────────────┐    │
       │ │order-service │  │payment-service│         │review-service│    │
       │ │  Port: 8005  │  │  Port: 8006  │          │  Port: 8007  │    │
       │ │ (2 Replicas) │  └──────┬───────┘          └──────────────┘    │
       │ └──────┬───────┘         │                                      │
       │        │                 ▼                                      │
       │        │          ┌──────────────┐          ┌──────────────┐    │
       │        │          │notif-service │          │recommendation│    │
       │        │          │  Port: 8009  │          │  Port: 8008  │    │
       │        │          └──────────────┘          └──────────────┘    │
       │        │                                                        │
       │        ▼                 ▼                         ▼            │
       │ ┌──────────────┐  ┌──────────────┐          ┌──────────────┐    │
       │ │analytics-svc │  │support-service│         │audit-service │    │
       │ │  Port: 8010  │  │  Port: 8011  │          │  Port: 8012  │    │
       │ └──────────────┘  └──────────────┘          └──────────────┘    │
       │        │                 │                         │            │
       │        └─────────────────┼─────────────────────────┘            │
       │                          ▼                                      │
       │          ┌───────────────────────────────┐                      │
       │          │ PersistentVolumeClaim (1Gi)   │                      │
       │          │        pad-data-pvc           │                      │
       │          └───────────────────────────────┘                      │
       └─────────────────────────────────────────────────────────────────┘
```

---

## 3. Используемые технологии

* **Контейнеризация:** Docker Engine 29+, Docker Compose v5+, Docker Buildx.
* **Базовый образ:** `python:3.12-slim` (минимизация attack surface, итоговый размер слоя приложения < 160MB).
* **Оркестрация:** Kubernetes v1.30+ / Minikube v1.36+.
* **Объекты K8s:** `Namespace`, `ConfigMap`, `Secret`, `Deployment`, `Service` (ClusterIP, NodePort), `PersistentVolumeClaim` (PVC).
* **Язык & Фреймворк:** Python 3.12, FastAPI, Uvicorn (ASGI), Pydantic v2.
* **Сетевой уровень:** HTTP/REST, JSON over TCP, CoreDNS cluster resolver.
* **Шлюз и статика:** Nginx Alpine / FastAPI Gateway Reverse Proxy с поддержкой SSE & Traffic Telemetry.
* **Хранилище & Кэш:** Persistent Volumes (POSIX JSON datastores), Redis 7 (Alpine).

---

## 4. Оптимизация Dockerfile

Каждый микросервис собирается в соответствии с лучшими практиками Docker:

```dockerfile
# Standalone Dockerfile for catalog-service
FROM python:3.12-slim

# 1. Запрет генерации .pyc байткода и принудительный unbuffered вывод
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8002

# 2. Принцип наименьших привилегий (Least Privilege):
# Создание непривилегированного пользователя и группы appuser (UID 10001)
RUN addgroup --system --gid 10001 appgroup && \
    adduser --system --uid 10001 --ingroup appgroup --no-create-home appuser

WORKDIR /app

# 3. Кэширование слоёв (Layer Caching):
# Установка зависимостей ДО копирования исходного кода
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Копирование только исходного кода сервиса
COPY . .

# 5. Подготовка каталога для постоянных данных с правами appuser
RUN mkdir -p /data && chown -R appuser:appgroup /data /app

# 6. Переключение на непривилегированного пользователя (Non-root user)
USER appuser

EXPOSE 8002

# 7. Контейнерный Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1

# 8. Точка входа
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

### Преимущества оптимизации:
1. **Безопасность:** В контейнере отсутствует `root`. Даже в случае уязвимости RCE злоумышленник не имеет доступа к хост-системе.
2. **Исключение мусора (`.dockerignore`):** Исключены `.git`, `__pycache__`, `.venv`, локальные логи и тесты.
3. **Отсутствие зашитых секретов:** Ключи JWT и токены передаются исключительно через Kubernetes Secrets и переменные окружения.
4. **Быстрая пересборка:** Слой `pip install` кэшируется и не пересобирается при изменении бизнес-логики.

---

## 5. Структура проекта

```text
pad-lab3/
├── README.md                      # Полная университетская документация и ответы к защите
├── Dockerfile                     # Корневой оптимизированный production Dockerfile
├── docker-compose.yml             # Полный стек из 14 контейнеров (1 команда)
├── requirements.txt               # Зависимости Python (FastAPI, Uvicorn, httpx, redis)
├── .dockerignore                  # Исключения сборки Docker
├── .gitignore                     # Исключения системы контроля версий Git
│
├── run_compose.bat                # 1-click запуск через Docker Compose
├── deploy_k8s.bat                 # 1-click развёртывание в Kubernetes (kubectl apply)
├── demo_scaling.bat               # Скрипт демонстрации масштабирования и self-healing
├── run_local.bat                  # Быстрый локальный запуск (dev_runner)
├── run_tunnel.bat                 # Внешний туннель Cloudflare для защиты
├── dev_runner.py                  # Оркестратор локальных ASGI-процессов
│
├── gateway/                       # API Gateway & Reverse Proxy
│   ├── Dockerfile                 # Образ шлюза
│   ├── nginx.conf                 # Nginx маршрутизация с CoreDNS резолвером
│   └── local_gateway.py           # Шлюз с API управления K8s и Traffic Stream
│
├── frontend/                      # Реактивный веб-интерфейс (SPA)
│   ├── index.html                 # Разметка SPA + вкладка "K8s Cluster"
│   ├── style.css                  # Dark-mode стили (Vercel/Linear aesthetic)
│   └── app.js                     # Клиентская логика, телеметрия кластера, масштабирование
│
├── services/                      # 12 микросервисов (каждый с Dockerfile)
│   ├── auth/                      # 8001: JWT, RBAC
│   ├── catalog/                   # 8002: Товары, остатки
│   ├── search/                    # 8003: Redis L1 Cache, фильтрация
│   ├── cart/                      # 8004: Корзина
│   ├── order/                     # 8005: Заказы
│   ├── payment/                   # 8006: Платежи
│   ├── review/                    # 8007: Отзывы
│   ├── recommendation/            # 8008: Рекомендации
│   ├── notification/              # 8009: Email/SMS логи
│   ├── analytics/                 # 8010: BI-аналитика
│   ├── support/                   # 8011: Тикеты поддержки
│   └── audit/                     # 8012: Журнал безопасности
│
└── k8s/                           # Манифесты Kubernetes
    ├── 00-namespace.yaml          # Пространство имён pad
    ├── 01-configmap.yaml          # URLs микросервисов, LOG_LEVEL
    ├── 02-secret.yaml             # JWT_SECRET, PAYMENT_GATEWAY_KEY (Base64)
    ├── 03-pvc.yaml                # PersistentVolumeClaim (1Gi)
    ├── 04-redis.yaml              # Redis Deployment + ClusterIP Service
    ├── 10-auth.yaml               # Deployment + Service
    ├── 11-catalog.yaml            # Deployment (2 replicas) + Service
    ├── 12-search.yaml             # Deployment + Service
    ├── 13-cart.yaml               # Deployment + Service
    ├── 14-order.yaml              # Deployment (2 replicas) + Service
    ├── 15-payment.yaml            # Deployment + Service
    ├── 16-review.yaml             # Deployment + Service
    ├── 17-recommendation.yaml     # Deployment + Service
    ├── 18-notification.yaml       # Deployment + Service
    ├── 19-analytics.yaml          # Deployment + Service
    ├── 20-support.yaml            # Deployment + Service
    ├── 21-audit.yaml              # Deployment + Service
    └── 30-gateway.yaml            # Gateway Deployment (2 replicas) + NodePort:30080
```

---

## 6. Установка и Запуск

### Вариант A. Развёртывание в Kubernetes / Minikube (Рекомендуется для защиты)

1. Запустите Minikube или включите Kubernetes в Docker Desktop:
   ```bash
   minikube start --driver=docker
   ```

2. Соберите базовые образы внутри Docker окружения Minikube:
   ```bash
   # Для Minikube: направить Docker CLI на демон внутри Minikube
   minikube -p minikube docker-env --shell powershell | Invoke-Expression

   # Сборка бэкенд-образа и шлюза
   docker build -t pad-backend:latest .
   docker build -t pad-gateway:latest -f gateway/Dockerfile .
   ```

3. Примените манифесты одной командой:
   ```bash
   deploy_k8s.bat
   # или вручную:
   kubectl apply -f k8s/
   ```

4. Откройте приложение:
   ```bash
   # Проброс порта NodePort Gateway на localhost:80
   kubectl port-forward svc/gateway-service 80:80 -n pad
   ```
   В браузере перейдите по адресу: `http://localhost:80` (или `http://<minikube-ip>:30080`).

---

### Вариант B. Запуск через Docker Compose

Поднять весь кластер из 14 контейнеров одной командой:
```bash
run_compose.bat
# или через CLI:
docker compose up --build
```
Веб-интерфейс и API шлюз доступны по адресу: `http://localhost:80`.

---

### Вариант C. Мгновенный запуск без контейнеров (Dev Runner)

```bash
run_local.bat
# или:
python dev_runner.py
```
Запускает все 12 микросервисов параллельно на портах 8001–8012 и API Gateway на 80.

---

## 7. Демонстрация на защите (Checklist преподавателя)

### 1. Проверка всех Pod'ов в Namespace `pad`:
```bash
kubectl get pods -n pad -o wide
```
*Ожидаемый результат:* Все 14–16 подов находятся в статусе `Running`, `Ready 1/1`, количество рестартов `0`.

### 2. Проверка сервисов и внутреннего CoreDNS:
```bash
kubectl get services -n pad
```
*Ожидаемый результат:* 13 сервисов типа `ClusterIP` с собственными внутренними IP-адресами (`10.96.x.x`), и `gateway-service` типа `NodePort` на порту `80:30080`.

### 3. Проверка развёртываний (Deployments):
```bash
kubectl get deployments -n pad
```
*Ожидаемый результат:* `catalog-service` и `order-service` имеют `2/2` готовых реплик, остальные сервисы `1/1`, `gateway-deployment` `2/2`.

### 4. Проверка логов пода:
```bash
kubectl logs -l app=order-service -n pad --tail=30
```

### 5. Демонстрация горизонтального масштабирования (Horizontal Pod Scaling):
```bash
# Масштабирование order-service с 2 до 4 реплик:
kubectl scale deployment order-service --replicas=4 -n pad

# Проверка создания новых реплик:
kubectl get pods -l app=order-service -n pad
```
*Наблюдение:* Kubernetes мгновенно создаёт 2 новых пода, запускает health checks и вводит их в пул балансировщика сервиса.

### 6. Демонстрация самовосстановления (Self-Healing / Fault Tolerance):
```bash
# Удаление одного из работающих подов:
kubectl delete pod <любой-order-service-pod> -n pad

# Проверка реакции ReplicaSet контроллера:
kubectl get pods -l app=order-service -n pad
```
*Наблюдение:* Kubernetes детектирует падение пода, переводит его в `Terminating` и одновременно поднимает новый здоровый под с новым хэшем. Сервис продолжает обслуживать трафик **без простоя (Zero Downtime)**.

### 7. Интерактивная демонстрация через Web UI:
Во вкладке **"K8s Cluster"** веб-интерфейса доступны интерактивные кнопки:
- **[Scale Up / Scale Down]** для каждого сервиса прямо из браузера.
- **[Kill Pod]** — симуляция аварии с визуальным наблюдением за циклом самовосстановления.
- **[kubectl Terminal]** — выполнение команд `get pods`, `get deployments`, `get svc` в реальном времени.

---

## 8. Ответы на теоретические вопросы преподавателя при защите

### В1: Чем Docker отличается от виртуальной машины (VM)?
* **Архитектура:** Виртуальная машина использует гипервизор (Type 1 или Type 2) и запускает полноценную гостевую операционную систему (Guest OS) со своим ядром, драйверами и системными службами (гигабайты памяти, минуты на старт).
* **Контейнер Docker:** Не содержит собственного ядра. Все контейнеры делят одно общее ядро хост-системы (Host Linux Kernel) и изолируются механизмами ядра:
  - `Namespaces` (изоляция PID, сетевых интерфейсов NET, файловой системы MNT, межпроцессного взаимодействия IPC, пользователей USER).
  - `Cgroups` (Control Groups — жёсткое ограничение и учёт ресурсов: CPU, RAM, I/O).
* **Преимущество:** Контейнеры запускаются за миллисекунды, весят десятки мегабайт и имеют практически нулевой оверхед по производительности процессора и памяти.

### В2: Зачем нужен Kubernetes и какие задачи он решает?
Docker умеет запускать отдельные контейнеры на одной машине. В распределённых production-системах из десятков сервисов возникают задачи, которые Docker сам по себе не решает:
1. **Self-Healing (Самовосстановление):** Если контейнер аварийно завершился или завис, Kubernetes автоматически перезапускает его или переносит на другой здоровый узел кластера.
2. **Auto-scaling (Автомасштабирование):** Горизонтальное масштабирование количества реплик (HPA) в зависимости от нагрузки по CPU/RAM или кастомным метрикам.
3. **Service Discovery & Load Balancing:** Kubernetes предоставляет единый виртуальный IP (ClusterIP) и DNS-имя для группы реплик, равномерно распределяя входящие запросы.
4. **Automated Rollouts & Rollbacks:** Плавное обновление сервисов (RollingUpdate) без остановки системы и мгновенный откат при ошибках.

### В3: Что делает Deployment?
`Deployment` — это декларативный контроллер высшего уровня в Kubernetes.
- Пользователь описывает желаемое состояние: *"Хочу 3 реплики образа `order-service:latest` с лимитом 300m CPU"*.
- Deployment управляет объектом `ReplicaSet`, который следит за точным количеством запущенных подов.
- При обновлении версии образа Deployment создаёт новый `ReplicaSet` и постепенно (по одной) заменяет старые реплики на новые (`RollingUpdate`), обеспечивая Zero Downtime.

### В4: Что делает Service и почему сервисы не общаются через localhost?
- В Kubernetes поды эфемерны: при падении, перезапуске или масштабировании старый под удаляется, создаётся новый, и его IP-адрес меняется.
- `Service` создаёт **стабильную абстракцию**: постоянный виртуальный IP-адрес (ClusterIP) и доменное имя в кластере (например, `http://catalog-service:8002`).
- Служба `kube-proxy` на узлах направляет трафик с виртуального ClusterIP на реальные IP-адреса живых подов через iptables/IPVS.
- `localhost` внутри пода указывает на сетевой стек самого контейнера. Если `order-service` обратится к `http://localhost:8002`, запрос останется внутри его собственного сетевого пространства имён, где `catalog-service` не запущен. Использование ClusterIP DNS гарантирует правильную маршрутизацию в кластере.

### В5: Зачем нужны ConfigMap и Secret?
Согласно принципам **12-Factor App (Раздел III. Конфигурация)**, конфигурация должна быть строго отделена от исполняемого кода:
- Один и тот же Docker-образ должен без изменений разворачиваться в средах Development, Staging и Production.
- `ConfigMap` хранит открытые параметры конфигурации (URL зависимых сервисов, уровни логирования, таймауты).
- `Secret` хранит конфиденциальные данные (JWT-ключи шифрования, API-токены платёжных систем, пароли к БД) в кодировке Base64 с защитой от непреднамеренного логирования и разделением прав доступа (RBAC).
- Параметры инжектируются в контейнеры как переменные окружения (`envFrom`) или монтируются как файлы в томах.

### В6: Что такое LivenessProbe и ReadinessProbe?
- **LivenessProbe (Проверка жизнеспособности):** Проверяет, не завис ли процесс (deadlock, out-of-memory). Если проба падает `failureThreshold` раз, kubelet принудительно убивает контейнер и перезапускает его согласно `restartPolicy`.
- **ReadinessProbe (Проверка готовности к трафику):** Проверяет, готов ли сервис принимать запросы клиентов (например, прогрелся ли кэш, установлено ли подключение к базе). Если проба не проходит, под не убивается, но его IP **временно исключается из Endpoints сервиса**, и балансировщик перестаёт отправлять на него клиентские запросы.

### В7: Что произойдёт при удалении одного Pod'а?
1. Администратор или сбой вызывает удаление пода: `kubectl delete pod order-service-xxx`.
2. Контроллер `ReplicaSet` в своём цикле реконсиляции (Reconciliation Loop) обнаруживает, что фактическое количество подов (1) меньше желаемого (2).
3. `ReplicaSet` немедленно обращается к kube-apiserver и запрашивает создание нового пода.
4. `kube-scheduler` выбирает подходящий узел с достаточными ресурсами CPU/RAM.
5. На узле `kubelet` скачивает образ, создаёт контейнер и запускает проверки готовности (`readinessProbe`).
6. После успешной проверки новый под добавляется в балансировщик `Service`, восстанавливая заданное количество реплик.

---

## 9. Результаты работы и Выводы

1. Все **12 микросервисов** распределённой платформы CloudMart успешно упакованы в оптимизированные Docker-образы с безопасным запуском от непривилегированного пользователя (`appuser`), многослойным кэшированием и контейнерными healthchecks.
2. Разработан и протестирован файл **`docker-compose.yml`**, позволяющий развернуть полный стек (14 контейнеров, общие сети, постоянные тома `pad_data`) одной командой.
3. Сформирована полная иерархия декларативных манифестов Kubernetes:
   - Изолированный `Namespace: pad`.
   - Конфигурации и секреты `ConfigMap` и `Secret`.
   - `PersistentVolumeClaim` для персистентности данных.
   - 13 `Deployments` с настроенными `resources.requests`, `resources.limits`, `livenessProbe` и `readinessProbe`.
   - 13 внутренних сервисов `ClusterIP` и внешний шлюз `NodePort:30080`.
4. Реализован интерактивный **Kubernetes Control Plane** во фронтенде с возможностью живого мониторинга подов, масштабирования реплик и тестирования самовосстановления.
5. Проведены тесты отказа и масштабирования: доказана высокая отказоустойчивость кластера при аварийном завершении подов и мгновенная реакция контроллера репликации.
