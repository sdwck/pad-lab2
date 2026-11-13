"""Unit and Integration Tests for All 12 CloudMart Microservices.

Validates service initialization, health probes, data validation,
repositories, business logic, and error handling across the entire stack.
"""

import json
import time

import pytest
from starlette.testclient import TestClient

from services.analytics.main import app as analytics_app
from services.audit.main import app as audit_app
from services.auth.main import app as auth_app
from services.cart.main import app as cart_app
from services.catalog.main import app as catalog_app
from services.notification.main import app as notification_app
from services.order.main import app as order_app
from services.payment.main import app as payment_app
from services.recommendation.main import app as recommendation_app
from services.review.main import app as review_app
from services.search.main import app as search_app
from services.support.main import app as support_app


# ---------------------------------------------------------
# 1. Health Probe Checks for All 12 Microservices
# ---------------------------------------------------------
@pytest.mark.parametrize(
    "app, expected_name",
    [
        (auth_app, "auth-service"),
        (catalog_app, "catalog-service"),
        (search_app, "search-service"),
        (cart_app, "cart-service"),
        (order_app, "order-service"),
        (payment_app, "payment-service"),
        (review_app, "review-service"),
        (recommendation_app, "recommendation-service"),
        (notification_app, "notification-service"),
        (analytics_app, "analytics-service"),
        (support_app, "support-service"),
        (audit_app, "audit-service"),
    ],
)
def test_microservices_health_check(app, expected_name):
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("service") == expected_name
    assert "version" in data


# ---------------------------------------------------------
# 2. Auth Microservice Tests
# ---------------------------------------------------------
def test_auth_registration_and_login():
    client = TestClient(auth_app)
    ts = int(time.time() * 1000)
    unique_user = f"user_{ts}"
    unique_email = f"user_{ts}@cloudmart.internal"

    # Register new user
    reg_res = client.post(
        "/register",
        json={
            "username": unique_user,
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Test Engineer",
            "role": "customer",
        },
    )
    assert reg_res.status_code in [200, 201]
    res_data = reg_res.json()
    user = res_data.get("user", res_data)
    assert user["email"] == unique_email
    assert "id" in user

    # Duplicate registration by email should fail
    dup_res = client.post(
        "/register",
        json={
            "username": f"{unique_user}_dup",
            "email": unique_email,
            "password": "AnotherPassword",
            "full_name": "Duplicate",
            "role": "customer",
        },
    )
    assert dup_res.status_code == 400

    # Login with correct credentials
    login_res = client.post(
        "/login",
        json={"email": unique_email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data or "token" in token_data
    token = token_data.get("access_token") or token_data.get("token")

    # Access protected /me endpoint
    me_res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == unique_email

    # Access protected /me with invalid token
    bad_me_res = client.get("/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert bad_me_res.status_code == 401


# ---------------------------------------------------------
# 3. Catalog Microservice Tests
# ---------------------------------------------------------
def test_catalog_retrieval_and_categories():
    client = TestClient(catalog_app)

    # Retrieve all products
    res = client.get("/products")
    assert res.status_code == 200
    products = res.json()
    assert isinstance(products, list)
    assert len(products) > 0

    first_product = products[0]
    assert "id" in first_product
    assert "title" in first_product
    assert "price" in first_product
    assert "category" in first_product

    # Retrieve by specific ID
    prod_id = first_product["id"]
    single_res = client.get(f"/products/{prod_id}")
    assert single_res.status_code == 200
    assert single_res.json()["id"] == prod_id

    # Retrieve categories
    cat_res = client.get("/categories")
    assert cat_res.status_code == 200
    categories = cat_res.json()
    assert isinstance(categories, list)
    assert first_product["category"] in categories


# ---------------------------------------------------------
# 4. Search & Filter Microservice Tests
# ---------------------------------------------------------
def test_search_service_query_and_filtering():
    client = TestClient(search_app)

    # Query search
    res = client.get("/search?q=pro")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data or "products" in data or "results" in data
    assert "cache_backend" in data

    # Check response headers (X-Cache telemetry)
    assert "X-Cache" in res.headers


# ---------------------------------------------------------
# 5. Cart Microservice Tests
# ---------------------------------------------------------
def test_cart_lifecycle():
    client = TestClient(cart_app)
    user_id = f"test_cart_user_{int(time.time() * 1000)}"

    # Verify initially empty or valid cart
    initial = client.get(f"/cart/{user_id}")
    assert initial.status_code == 200
    assert initial.json()["user_id"] == user_id

    # Add item
    add_res = client.post(
        f"/cart/{user_id}/items",
        json={
            "product_id": "prod_lap_01",
            "title": "MacBook Pro 16",
            "price": 2499.00,
            "quantity": 1,
            "image_url": "https://example.com/laptop.jpg",
        },
    )
    assert add_res.status_code == 200
    cart = add_res.json()
    assert len(cart["items"]) >= 1
    assert cart["total_price"] >= 2499.00

    # Update item quantity
    update_res = client.put(f"/cart/{user_id}/items/prod_lap_01", json={"quantity": 3})
    assert update_res.status_code == 200
    updated_cart = update_res.json()
    item = next(it for it in updated_cart["items"] if it["product_id"] == "prod_lap_01")
    assert item["quantity"] == 3

    # Remove item
    del_res = client.delete(f"/cart/{user_id}/items/prod_lap_01")
    assert del_res.status_code == 200
    final_cart = del_res.json()
    assert not any(it["product_id"] == "prod_lap_01" for it in final_cart["items"])


# ---------------------------------------------------------
# 6. Order Microservice Tests
# ---------------------------------------------------------
def test_order_creation_and_status():
    client = TestClient(order_app)
    user_id = f"order_user_{int(time.time() * 1000)}"

    order_payload = {
        "user_id": user_id,
        "customer_name": "Test Customer",
        "customer_email": "customer@cloudmart.internal",
        "shipping_address": "100 Innovation Way, Silicon Valley, CA",
        "items": [
            {
                "product_id": "prod_kb_01",
                "title": "Mechanical Keyboard",
                "price": 199.00,
                "quantity": 2,
            }
        ],
    }

    create_res = client.post("/orders", json=order_payload)
    assert create_res.status_code in [200, 201]
    order = create_res.json()
    assert order["user_id"] == user_id
    assert order["total_amount"] == 398.00
    assert order["status"] == "PENDING_PAYMENT"
    order_id = order["id"]

    # Fetch order by ID
    get_res = client.get(f"/orders/{order_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == order_id

    # Update order status
    status_res = client.patch(f"/orders/{order_id}/status", json={"status": "PAID"})
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "PAID"


# ---------------------------------------------------------
# 7. Payment Microservice Tests
# ---------------------------------------------------------
def test_payment_processing():
    client = TestClient(payment_app)
    order_id = f"ord_{int(time.time() * 1000)}"
    user_id = f"usr_{int(time.time() * 1000)}"

    payment_payload = {
        "order_id": order_id,
        "user_id": user_id,
        "amount": 398.00,
        "card_number": "4532750012345678",
        "card_holder": "Alexander Vance",
        "exp_month": "12",
        "exp_year": "2028",
        "cvv": "321",
    }

    res = client.post("/payments/process", json=payment_payload)
    assert res.status_code == 200
    receipt = res.json()
    assert receipt["order_id"] == order_id
    assert receipt["status"] == "SUCCESS"
    tx_id = receipt.get("transaction_id") or receipt.get("id")
    assert tx_id is not None

    # Verify transaction lookup
    lookup_res = client.get(f"/payments/{tx_id}")
    assert lookup_res.status_code == 200
    fetched_tx = lookup_res.json()
    assert (fetched_tx.get("transaction_id") or fetched_tx.get("id")) == tx_id


# ---------------------------------------------------------
# 8. Review Microservice Tests
# ---------------------------------------------------------
def test_review_submission_and_aggregation():
    client = TestClient(review_app)
    prod_id = f"prod_review_test_{int(time.time() * 1000)}"

    review_payload = {
        "product_id": prod_id,
        "user_id": "usr_tester_99",
        "user_name": "Senior LQA Auditor",
        "rating": 5,
        "comment": "Exceptional reliability and responsive throughput under load.",
    }

    res = client.post("/reviews", json=review_payload)
    assert res.status_code in [200, 201]
    review = res.json()
    assert review["product_id"] == prod_id
    assert review["rating"] == 5

    # List reviews for product
    list_res = client.get(f"/reviews/product/{prod_id}")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # Check stats
    stats_res = client.get(f"/reviews/stats/{prod_id}")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["average_rating"] == 5.0
    assert stats["total_reviews"] >= 1


# ---------------------------------------------------------
# 9. Recommendation Microservice Tests
# ---------------------------------------------------------
def test_recommendation_endpoints():
    client = TestClient(recommendation_app)

    trending_res = client.get("/recommendations/trending")
    assert trending_res.status_code == 200
    assert isinstance(trending_res.json(), list)

    prod_res = client.get("/recommendations/product/prod_01")
    assert prod_res.status_code == 200
    assert isinstance(prod_res.json(), list)


# ---------------------------------------------------------
# 10. Notification Microservice Tests
# ---------------------------------------------------------
def test_notification_delivery():
    client = TestClient(notification_app)
    user_id = f"notif_user_{int(time.time() * 1000)}"

    payload = {
        "user_id": user_id,
        "type": "ORDER",
        "title": "Cluster Provisioning Notification",
        "message": "All Kubernetes nodes are running with 100% capacity.",
    }

    send_res = client.post("/notifications/send", json=payload)
    assert send_res.status_code in [200, 201]
    notif = send_res.json()
    assert notif["user_id"] == user_id
    assert notif["is_read"] is False

    # List notifications
    list_res = client.get(f"/notifications/user/{user_id}")
    assert list_res.status_code == 200
    assert any(n["id"] == notif["id"] for n in list_res.json())


# ---------------------------------------------------------
# 11. Support Microservice Tests
# ---------------------------------------------------------
def test_support_ticket_lifecycle():
    client = TestClient(support_app)
    user_id = f"supp_user_{int(time.time() * 1000)}"

    create_payload = {
        "user_id": user_id,
        "user_name": "DevOps Architect",
        "subject": "CoreDNS resolution latency inquiry",
        "priority": "normal",
        "initial_message": "Can we configure dnsConfig ndots: 2 in pod spec?",
    }

    tkt_res = client.post("/tickets", json=create_payload)
    assert tkt_res.status_code in [200, 201]
    ticket = tkt_res.json()
    tkt_id = ticket["id"]
    assert ticket["status"] == "OPEN"

    # Add reply message
    reply_res = client.post(
        f"/tickets/{tkt_id}/messages",
        json={
            "sender_name": "Site Reliability Engineer",
            "is_staff": True,
            "text": "Yes, ndots:2 reduces DNS lookups.",
        },
    )
    assert reply_res.status_code == 200
    assert len(reply_res.json()["messages"]) == 2

    # Resolve ticket
    res_ticket = client.patch(f"/tickets/{tkt_id}/resolve")
    assert res_ticket.status_code == 200
    assert res_ticket.json()["status"] == "RESOLVED"


# ---------------------------------------------------------
# 12. Distributed Audit Microservice Tests
# ---------------------------------------------------------
def test_audit_logging_and_filtering():
    client = TestClient(audit_app)
    uid = f"audit_usr_{int(time.time() * 1000)}"

    log_entry = {
        "service": "k8s-controller",
        "action": "POD_SCALE_RECONCILE",
        "user_id": uid,
        "details": json.dumps({"previous_replicas": 2, "target_replicas": 4}),
        "ip_address": "10.244.0.1",
    }

    post_res = client.post("/audit/log", json=log_entry)
    assert post_res.status_code in [200, 201]
    entry = post_res.json()
    assert entry["action"] == "POD_SCALE_RECONCILE"
    assert entry["service"] == "k8s-controller"

    # Filter logs
    filtered_res = client.get("/audit/logs?service=k8s-controller")
    assert filtered_res.status_code == 200
    assert any(log["id"] == entry["id"] for log in filtered_res.json())


# ---------------------------------------------------------
# 13. Analytics Microservice Tests
# ---------------------------------------------------------
def test_analytics_dashboard_metrics():
    client = TestClient(analytics_app)
    res = client.get("/analytics/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "total_revenue" in data
    assert "total_orders" in data
    assert "top_products" in data
