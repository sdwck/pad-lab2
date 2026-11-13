"""Full End-to-End (E2E) Integration Test Suite.

Simulates the complete end-to-end customer checkout and operations lifecycle:
1. User Registration & Authentication (JWT issuance)
2. Catalog Discovery & Stock Inspection
3. Full-Text Search with Telemetry Caching
4. Cart State Management (Add, Update quantity, Verify total)
5. Algorithmic Recommendations
6. Order Creation & State Tracking
7. Payment Gateway Processing (Card validation, receipt issuance)
8. Order Fulfillment State Transition (PENDING -> PAID)
9. Notification Dispatch (Order receipt event)
10. Immutable Audit Logging (Security & regulatory compliance)
11. Customer Product Review & Rating Aggregation
12. Customer Support Ticket Lifecycle
13. BI Business Analytics & Metric Ingestion
"""

import json
import time

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


def test_complete_e2e_customer_checkout_journey():
    # Instantiate clients for all microservices in the pipeline
    auth_cli = TestClient(auth_app)
    cat_cli = TestClient(catalog_app)
    search_cli = TestClient(search_app)
    cart_cli = TestClient(cart_app)
    order_cli = TestClient(order_app)
    pay_cli = TestClient(payment_app)
    rec_cli = TestClient(recommendation_app)
    notif_cli = TestClient(notification_app)
    audit_cli = TestClient(audit_app)
    review_cli = TestClient(review_app)
    supp_cli = TestClient(support_app)
    analytics_cli = TestClient(analytics_app)

    unique_ts = int(time.time() * 1000)
    customer_username = f"e2e_buyer_{unique_ts}"
    customer_email = f"buyer_{unique_ts}@cloudmart.internal"
    customer_name = "Alexandre V. Dumont"

    # Step 1: User Registration
    reg_res = auth_cli.post(
        "/register",
        json={
            "username": customer_username,
            "email": customer_email,
            "password": "StrongMasterPassword2026!",
            "full_name": customer_name,
            "role": "customer",
        },
    )
    assert reg_res.status_code in [200, 201]
    reg_body = reg_res.json()
    user_record = reg_body.get("user", reg_body)
    user_id = user_record["id"]
    assert user_record["email"] == customer_email

    # Step 2: Authentication & Token Issuance
    login_res = auth_cli.post(
        "/login",
        json={"email": customer_email, "password": "StrongMasterPassword2026!"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    jwt_token = token_data.get("access_token") or token_data.get("token")
    assert jwt_token is not None

    # Step 3: Browse Catalog
    catalog_res = cat_cli.get("/products")
    assert catalog_res.status_code == 200
    all_products = catalog_res.json()
    assert len(all_products) >= 2
    selected_prod = all_products[0]
    prod_id = selected_prod["id"]
    prod_price = float(selected_prod["price"])

    # Step 4: Search Service Query
    search_res = search_cli.get(f"/search?q={selected_prod['title'].split()[0]}")
    assert search_res.status_code == 200
    assert "cache_backend" in search_res.json()

    # Step 5: Add to Cart
    add_cart_res = cart_cli.post(
        f"/cart/{user_id}/items",
        json={
            "product_id": prod_id,
            "title": selected_prod["title"],
            "price": prod_price,
            "quantity": 2,
            "image_url": selected_prod.get("image_url", ""),
        },
    )
    assert add_cart_res.status_code == 200
    current_cart = add_cart_res.json()
    expected_cart_total = round(prod_price * 2, 2)
    assert current_cart["total_price"] >= expected_cart_total

    # Step 6: View Personalized Recommendations
    rec_res = rec_cli.get("/recommendations/trending")
    assert rec_res.status_code == 200
    assert isinstance(rec_res.json(), list)

    # Step 7: Place Order
    order_res = order_cli.post(
        "/orders",
        json={
            "user_id": user_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "shipping_address": "42 Boulevard de la Liberté, Paris",
            "items": [
                {
                    "product_id": prod_id,
                    "title": selected_prod["title"],
                    "price": prod_price,
                    "quantity": 2,
                }
            ],
        },
    )
    assert order_res.status_code in [200, 201]
    created_order = order_res.json()
    order_id = created_order["id"]
    assert created_order["status"] == "PENDING_PAYMENT"
    assert created_order["total_amount"] == expected_cart_total

    # Step 8: Execute Payment via Payment Microservice
    pay_res = pay_cli.post(
        "/payments/process",
        json={
            "order_id": order_id,
            "user_id": user_id,
            "amount": expected_cart_total,
            "card_number": "4242424242424242",
            "card_holder": customer_name,
            "exp_month": "11",
            "exp_year": "2029",
            "cvv": "789",
        },
    )
    assert pay_res.status_code == 200
    payment_receipt = pay_res.json()
    assert payment_receipt["status"] == "SUCCESS"
    tx_id = payment_receipt.get("transaction_id") or payment_receipt.get("id")
    assert tx_id is not None

    # Step 9: Reconcile Order State (Transition to PAID)
    update_order_res = order_cli.patch(
        f"/orders/{order_id}/status",
        json={"status": "PAID"},
    )
    assert update_order_res.status_code == 200
    assert update_order_res.json()["status"] == "PAID"

    # Step 10: Dispatch Order Confirmation Notification
    notif_res = notif_cli.post(
        "/notifications/send",
        json={
            "user_id": user_id,
            "type": "ORDER",
            "title": f"Order {order_id} Confirmed",
            "message": f"Payment of ${expected_cart_total} approved. Tracking TX: {tx_id}",
        },
    )
    assert notif_res.status_code in [200, 201]
    notif_id = notif_res.json()["id"]

    # Verify notification received
    user_notifs_res = notif_cli.get(f"/notifications/user/{user_id}")
    assert user_notifs_res.status_code == 200
    assert any(n["id"] == notif_id for n in user_notifs_res.json())

    # Step 11: Write Audit Log for Compliance & Security
    audit_res = audit_cli.post(
        "/audit/log",
        json={
            "service": "checkout-orchestrator",
            "action": "ORDER_PAYMENT_FULFILLED",
            "user_id": user_id,
            "details": json.dumps({"order_id": order_id, "amount": expected_cart_total, "tx_id": tx_id}),
            "ip_address": "192.168.1.100",
        },
    )
    assert audit_res.status_code in [200, 201]

    # Step 12: Customer Leaves Verified Purchase Review
    review_res = review_cli.post(
        "/reviews",
        json={
            "product_id": prod_id,
            "user_id": user_id,
            "user_name": customer_name,
            "rating": 5,
            "comment": "Flawless end-to-end purchasing experience and swift order fulfillment!",
        },
    )
    assert review_res.status_code in [200, 201]

    # Verify product rating statistics updated
    stats_res = review_cli.get(f"/reviews/stats/{prod_id}")
    assert stats_res.status_code == 200
    assert stats_res.json()["total_reviews"] >= 1

    # Step 13: Customer Submits Support Inquiry
    supp_res = supp_cli.post(
        "/tickets",
        json={
            "user_id": user_id,
            "user_name": customer_name,
            "subject": f"Inquiry regarding order {order_id}",
            "priority": "normal",
            "initial_message": "Could you provide international tracking reference?",
        },
    )
    assert supp_res.status_code in [200, 201]
    ticket_id = supp_res.json()["id"]

    # Staff agent answers support inquiry
    reply_res = supp_cli.post(
        f"/tickets/{ticket_id}/messages",
        json={
            "sender_name": "Senior Logistics Coordinator",
            "is_staff": True,
            "text": "Your package has been dispatched via DHL Express with express air telemetry.",
        },
    )
    assert reply_res.status_code == 200
    assert len(reply_res.json()["messages"]) == 2

    # Step 14: BI Analytics Ingestion
    dash_res = analytics_cli.get("/analytics/dashboard")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "total_revenue" in dash_data
    assert "total_orders" in dash_data
