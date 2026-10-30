/**
 * CloudMart • Pure Minimalist Architecture Client
 * Pattern: MVVM (Model - View - ViewModel)
 */

// ==========================================
// 1. MODEL
// ==========================================
class StoreModel {
    constructor() {
        this.currentUser = null;
        this.token = localStorage.getItem("pad_jwt") || null;
        this.products = [];
        this.categories = [];
        this.cart = { items: [], total_price: 0, items_count: 0 };
        this.orders = [];
        this.analytics = null;
        this.tickets = [];
        this.auditLogs = [];
        this.recommendations = [];
        this.selectedProductId = null;
        this.servicesMesh = [
            {
                id: "catalog",
                name: "catalog-service",
                port: 8002,
                domain: "Storefront",
                pattern: "Repository + Service",
                db: "catalog_data.json",
                desc: "Hardware inventory, specifications, pricing and stock mutations.",
                deps: "Called by: search, recommendations, order, analytics"
            },
            {
                id: "search",
                name: "search-service",
                port: 8003,
                domain: "Storefront",
                pattern: "Cache-Aside (Redis / TTL)",
                db: "in-memory TTL cache",
                desc: "Multi-facet hardware search with sub-millisecond TTL response caching.",
                deps: "Calls: catalog-service :8002"
            },
            {
                id: "recommendations",
                name: "recommendation-service",
                port: 8008,
                domain: "Storefront",
                pattern: "Content Affinity",
                db: "affinity scoring table",
                desc: "Tag and category pairing heuristics to compute related accessories.",
                deps: "Calls: catalog-service :8002"
            },
            {
                id: "reviews",
                name: "review-service",
                port: 8007,
                domain: "Storefront",
                pattern: "Aggregator",
                db: "reviews_data.json",
                desc: "Customer review distribution, verified ratings and score calculation.",
                deps: "Called by: Gateway / Web Client"
            },
            {
                id: "cart",
                name: "cart-service",
                port: 8004,
                domain: "Transactions",
                pattern: "Session Store",
                db: "cart_data.json",
                desc: "Session-bound ephemeral basket with automatic fallback handling.",
                deps: "Called by: Gateway / Web Client"
            },
            {
                id: "orders",
                name: "order-service",
                port: 8005,
                domain: "Transactions",
                pattern: "Finite State Machine",
                db: "orders_data.json",
                desc: "Order lifecycle: PENDING_PAYMENT -> PAID -> SHIPPED with item snapshots.",
                deps: "Calls: catalog :8002, notification :8009, audit :8012"
            },
            {
                id: "payments",
                name: "payment-service",
                port: 8006,
                domain: "Transactions",
                pattern: "Transaction Ledger",
                db: "payments_data.json",
                desc: "Mock payment validation, ledger recording and order transition.",
                deps: "Calls: order :8005, notification :8009, audit :8012"
            },
            {
                id: "auth",
                name: "auth-service",
                port: 8001,
                domain: "Platform",
                pattern: "JWT Claims + Auth",
                db: "users_data.json",
                desc: "User credential verification, role-based claims and token issuing.",
                deps: "Called by: Gateway / Web Client"
            },
            {
                id: "audit",
                name: "audit-service",
                port: 8012,
                domain: "Platform",
                pattern: "Append-Only Ledger",
                db: "audit_data.json",
                desc: "Centralized tamper-evident chronological security and activity trail.",
                deps: "Called by: order, payment, auth"
            },
            {
                id: "notifications",
                name: "notification-service",
                port: 8009,
                domain: "Platform",
                pattern: "Event Dispatcher",
                db: "notifications_data.json",
                desc: "Simulated asynchronous email & SMS event dispatching.",
                deps: "Called by: order, payment"
            },
            {
                id: "analytics",
                name: "analytics-service",
                port: 8010,
                domain: "Platform",
                pattern: "Cross-Service Query",
                db: "computed BI rollup",
                desc: "Calculates gross merchandise value, average order value and top units.",
                deps: "Calls: order-service :8005, catalog :8002"
            },
            {
                id: "support",
                name: "support-service",
                port: 8011,
                domain: "Platform",
                pattern: "Conversation Thread",
                db: "support_data.json",
                desc: "Customer support ticketing system with message thread lifecycle.",
                deps: "Called by: Gateway / Web Client"
            }
        ];
    }
}

// ==========================================
// 2. VIEWMODEL
// ==========================================
class StoreViewModel {
    constructor(model) {
        this.model = model;
        this.apiBase = "/api";
    }

    async init() {
        if (this.model.token) {
            await this.restoreSession();
        }

        await Promise.allSettled([
            this.fetchCategories(),
            this.searchProducts(""),
            this.fetchRecommendations(),
            this.fetchCart(),
            this.fetchOrders(),
            this.fetchAnalytics(),
            this.fetchTickets(),
            this.fetchAuditLogs()
        ]);
    }

    async restoreSession() {
        try {
            const res = await fetch(`${this.apiBase}/auth/me`, {
                headers: { "Authorization": `Bearer ${this.model.token}` }
            });
            if (res.ok) {
                this.model.currentUser = await res.json();
            } else {
                this.logout();
            }
        } catch (e) {
            console.warn("Auth check:", e);
        }
    }

    async login(email, password) {
        const res = await fetch(`${this.apiBase}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Invalid credentials");
        }

        const data = await res.json();
        this.model.token = data.token;
        this.model.currentUser = data.user;
        localStorage.setItem("pad_jwt", data.token);

        await Promise.allSettled([
            this.fetchCart(),
            this.fetchOrders(),
            this.fetchTickets()
        ]);

        return data.user;
    }

    async register(fullName, username, email, password) {
        const res = await fetch(`${this.apiBase}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ full_name: fullName, username, email, password })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Registration failed");
        }

        const data = await res.json();
        this.model.token = data.token;
        this.model.currentUser = data.user;
        localStorage.setItem("pad_jwt", data.token);

        await Promise.allSettled([
            this.fetchCart(),
            this.fetchOrders()
        ]);

        return data.user;
    }

    logout() {
        this.model.currentUser = null;
        this.model.token = null;
        localStorage.removeItem("pad_jwt");
        this.model.cart = { items: [], total_price: 0, items_count: 0 };
        this.model.orders = [];
    }

    getEffectiveUserId() {
        return this.model.currentUser ? this.model.currentUser.id : "guest_session";
    }

    async fetchCategories() {
        try {
            const res = await fetch(`${this.apiBase}/catalog/categories`);
            if (res.ok) this.model.categories = await res.json();
        } catch (e) {}
    }

    async searchProducts(q = "", category = "", sortBy = "") {
        const start = performance.now();
        try {
            const params = new URLSearchParams();
            if (q) params.set("q", q);
            if (category) params.set("category", category);
            if (sortBy) params.set("sort_by", sortBy);

            const res = await fetch(`${this.apiBase}/search/search?${params.toString()}`);
            if (res.ok) {
                const data = await res.json();
                this.model.products = data.items || [];
                const cacheHeader = res.headers.get("X-Cache") || (data.cached ? "HIT" : "MISS");
                const backend = data.cache_backend || "Redis";
                return {
                    cached: data.cached,
                    cacheHeader,
                    backend,
                    latency: data.latency_ms || Math.round((performance.now() - start) * 10) / 10
                };
            }
        } catch (e) {}
        return { cached: false, cacheHeader: "MISS", backend: "None", latency: 0 };
    }

    async fetchCart() {
        const uid = this.getEffectiveUserId();
        try {
            const res = await fetch(`${this.apiBase}/cart/cart/${uid}`);
            if (res.ok) this.model.cart = await res.json();
        } catch (e) {}
    }

    async addToCart(product) {
        const uid = this.getEffectiveUserId();
        try {
            const res = await fetch(`${this.apiBase}/cart/cart/${uid}/items`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    product_id: product.id,
                    title: product.title,
                    price: product.price,
                    quantity: 1,
                    image_url: product.image_url
                })
            });
            if (res.ok) {
                this.model.cart = await res.json();
                return true;
            }
        } catch (e) {}
        return false;
    }

    async updateCartQty(productId, newQty) {
        const uid = this.getEffectiveUserId();
        try {
            const res = await fetch(`${this.apiBase}/cart/cart/${uid}/items/${productId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ quantity: newQty })
            });
            if (res.ok) {
                this.model.cart = await res.json();
                return true;
            }
        } catch (e) {}
        return false;
    }

    async removeFromCart(productId) {
        const uid = this.getEffectiveUserId();
        try {
            const res = await fetch(`${this.apiBase}/cart/cart/${uid}/items/${productId}`, { method: "DELETE" });
            if (res.ok) {
                this.model.cart = await res.json();
                return true;
            }
        } catch (e) {}
        return false;
    }

    async clearCart() {
        const uid = this.getEffectiveUserId();
        try {
            const res = await fetch(`${this.apiBase}/cart/cart/${uid}`, { method: "DELETE" });
            if (res.ok) {
                this.model.cart = await res.json();
                return true;
            }
        } catch (e) {}
        return false;
    }

    async checkout(shippingAddress, cardInfo) {
        if (!this.model.currentUser) throw new Error("AUTH_REQUIRED");
        if (!this.model.cart.items || this.model.cart.items.length === 0) throw new Error("Cart is empty");

        const user = this.model.currentUser;

        // Order call
        const orderRes = await fetch(`${this.apiBase}/orders/orders`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: user.id,
                customer_name: user.full_name,
                customer_email: user.email,
                shipping_address: shippingAddress,
                items: this.model.cart.items.map(i => ({
                    product_id: i.product_id,
                    title: i.title,
                    price: i.price,
                    quantity: i.quantity
                }))
            })
        });

        if (!orderRes.ok) {
            const err = await orderRes.text();
            throw new Error(`Order failed: ${err}`);
        }

        const order = await orderRes.json();

        // Payment call
        const payRes = await fetch(`${this.apiBase}/payments/payments/process`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                order_id: order.id,
                user_id: user.id,
                amount: order.total_amount,
                card_number: cardInfo.cardNumber,
                card_holder: user.full_name,
                exp_month: cardInfo.expMonth || "12",
                exp_year: cardInfo.expYear || "28",
                cvv: cardInfo.cardCvv
            })
        });

        if (!payRes.ok) {
            const err = await payRes.text();
            throw new Error(`Payment failed: ${err}`);
        }

        await this.clearCart();
        await this.fetchOrders();
        await this.fetchAnalytics();
        await this.fetchAuditLogs();

        return order;
    }

    async fetchOrders() {
        if (!this.model.currentUser) {
            this.model.orders = [];
            return;
        }
        try {
            const res = await fetch(`${this.apiBase}/orders/orders/user/${this.model.currentUser.id}`);
            if (res.ok) this.model.orders = await res.json();
        } catch (e) {}
    }

    async fetchAnalytics() {
        try {
            const res = await fetch(`${this.apiBase}/analytics/analytics/dashboard`);
            if (res.ok) this.model.analytics = await res.json();
        } catch (e) {}
    }

    async fetchRecommendations() {
        try {
            const res = await fetch(`${this.apiBase}/recommendations/recommendations/trending`);
            if (res.ok) this.model.recommendations = await res.json();
        } catch (e) {}
    }

    async fetchTickets() {
        if (!this.model.currentUser) {
            this.model.tickets = [];
            return;
        }
        try {
            const res = await fetch(`${this.apiBase}/support/tickets/user/${this.model.currentUser.id}`);
            if (res.ok) this.model.tickets = await res.json();
        } catch (e) {}
    }

    async createTicket(subject, priority, message) {
        if (!this.model.currentUser) throw new Error("AUTH_REQUIRED");
        const user = this.model.currentUser;
        const res = await fetch(`${this.apiBase}/support/tickets`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: user.id,
                user_name: user.full_name,
                subject,
                priority,
                initial_message: message
            })
        });
        if (res.ok) {
            await this.fetchTickets();
            return true;
        }
        return false;
    }

    async fetchAuditLogs() {
        try {
            const res = await fetch(`${this.apiBase}/audit/audit/logs?limit=30`);
            if (res.ok) this.model.auditLogs = await res.json();
        } catch (e) {}
    }

    async fetchProductReviews(productId) {
        this.model.selectedProductId = productId;
        try {
            const [revRes, statsRes] = await Promise.all([
                fetch(`${this.apiBase}/reviews/reviews/product/${productId}`),
                fetch(`${this.apiBase}/reviews/reviews/stats/${productId}`)
            ]);
            const reviews = revRes.ok ? await revRes.json() : [];
            const stats = statsRes.ok ? await statsRes.json() : null;
            return { reviews, stats };
        } catch (e) {
            return { reviews: [], stats: null };
        }
    }

    async submitReview(productId, rating, comment) {
        if (!this.model.currentUser) throw new Error("AUTH_REQUIRED");
        const res = await fetch(`${this.apiBase}/reviews/reviews`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                product_id: productId,
                user_id: this.model.currentUser.id,
                user_name: this.model.currentUser.full_name,
                rating: parseInt(rating),
                comment
            })
        });
        return res.ok;
    }

    async probeCluster() {
        const results = {};
        await Promise.all(this.model.servicesMesh.map(async (svc) => {
            const start = performance.now();
            try {
                let signal;
                if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
                    signal = AbortSignal.timeout(3500);
                } else {
                    const ctrl = new AbortController();
                    setTimeout(() => ctrl.abort(), 3500);
                    signal = ctrl.signal;
                }
                const res = await fetch(`${this.apiBase}/${svc.id}/health?_t=${Date.now()}`, { 
                    signal, 
                    cache: "no-store" 
                });
                const dur = Math.max(1, Math.round(performance.now() - start));
                results[svc.id] = { status: res.ok ? "UP" : "ERR", latency: dur };
            } catch (e) {
                console.warn(`Probe failed for ${svc.id}:`, e);
                results[svc.id] = { status: "DOWN", latency: 0 };
            }
        }));
        return results;
    }

    async fetchTrafficLogs() {
        try {
            const res = await fetch(`${this.apiBase}/stream/traffic?limit=80`);
            if (res.ok) {
                return await res.json();
            }
        } catch (e) {
            console.warn("Traffic fetch error:", e);
        }
        return [];
    }

    async clearTrafficLogs() {
        try {
            await fetch(`${this.apiBase}/stream/traffic`, { method: "DELETE" });
        } catch (e) {
            console.warn("Traffic clear error:", e);
        }
    }
}

// ==========================================
// 3. VIEW
// ==========================================
class StoreView {
    constructor(viewModel) {
        this.vm = viewModel;
        this.trafficLogs = [];
        this.trafficTimer = null;
        this.trafficPaused = false;
        this.expandedLogIds = new Set();
        this.bindEvents();
    }

    showToast(msg) {
        const tray = document.getElementById("toastContainer");
        const el = document.createElement("div");
        el.className = "toast-msg";
        el.textContent = msg;
        tray.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    }

    bindEvents() {
        // Tab routing
        document.querySelectorAll(".tab-link").forEach(btn => {
            btn.addEventListener("click", () => {
                const tab = btn.dataset.tab;
                document.querySelectorAll(".tab-link").forEach(b => b.classList.remove("active"));
                document.querySelectorAll(".tab-page").forEach(p => p.classList.remove("active"));
                btn.classList.add("active");
                document.getElementById(`tab-${tab}`).classList.add("active");

                if (tab === "orders") this.renderOrders();
                if (tab === "analytics") this.renderAnalytics();
                if (tab === "support") this.renderSupport();
                if (tab === "audit") this.renderAuditLogs();
                if (tab === "topology") this.renderMesh();
                if (tab === "traffic") {
                    this.startTrafficStream();
                } else {
                    this.stopTrafficStream();
                }
            });
        });

        // Traffic controls
        const pauseBtn = document.getElementById("trafficPauseBtn");
        if (pauseBtn) {
            pauseBtn.addEventListener("click", () => {
                this.trafficPaused = !this.trafficPaused;
                pauseBtn.textContent = this.trafficPaused ? "Resume Stream" : "Pause Stream";
                if (!this.trafficPaused) {
                    this.pollTraffic();
                }
            });
        }

        const clearBtn = document.getElementById("clearTrafficBtn");
        if (clearBtn) {
            clearBtn.addEventListener("click", async () => {
                await this.vm.clearTrafficLogs();
                this.trafficLogs = [];
                this.renderTraffic();
                this.showToast("Traffic stream buffer cleared");
            });
        }

        const filterInput = document.getElementById("trafficFilterInput");
        if (filterInput) {
            filterInput.addEventListener("input", () => this.renderTraffic());
        }

        const methodFilter = document.getElementById("trafficMethodFilter");
        if (methodFilter) {
            methodFilter.addEventListener("change", () => this.renderTraffic());
        }

        // Search
        document.getElementById("applySearchBtn").addEventListener("click", () => this.handleSearch());
        const searchInput = document.getElementById("searchInput");
        searchInput.addEventListener("keyup", (e) => {
            if (e.key === "Enter") this.handleSearch();
        });

        // Card field input formatters (prevents broken MM/YY entry)
        const expInput = document.getElementById("cardExp");
        if (expInput) {
            expInput.addEventListener("input", (e) => {
                let v = e.target.value.replace(/[^\d/]/g, "");
                if (!v.includes("/")) {
                    if (v.length > 4) v = v.slice(0, 4);
                    if (v.length >= 3) {
                        v = v.slice(0, 2) + "/" + v.slice(2);
                    }
                } else {
                    const parts = v.split("/");
                    const m = parts[0].slice(0, 2);
                    const y = (parts[1] || "").slice(0, 2);
                    v = parts.length > 1 ? `${m}/${y}` : m;
                }
                e.target.value = v;
            });
        }

        const cardInput = document.getElementById("cardNumber");
        if (cardInput) {
            cardInput.addEventListener("input", (e) => {
                let v = e.target.value.replace(/\D/g, "");
                if (v.length > 16) v = v.slice(0, 16);
                const parts = v.match(/.{1,4}/g);
                e.target.value = parts ? parts.join(" ") : v;
            });
        }

        const cvvInput = document.getElementById("cardCvv");
        if (cvvInput) {
            cvvInput.addEventListener("input", (e) => {
                e.target.value = e.target.value.replace(/\D/g, "").slice(0, 4);
            });
        }

        // Cart Actions
        document.getElementById("clearCartBtn").addEventListener("click", async () => {
            await this.vm.clearCart();
            this.renderCart();
            this.showToast("Cart emptied");
        });

        document.getElementById("checkoutBtn").addEventListener("click", () => this.handleCheckout());

        // Refresh triggers
        document.getElementById("refreshOrdersBtn").addEventListener("click", async () => {
            await this.vm.fetchOrders();
            this.renderOrders();
            this.showToast("Orders updated");
        });

        document.getElementById("refreshAnalyticsBtn").addEventListener("click", async () => {
            await this.vm.fetchAnalytics();
            this.renderAnalytics();
            this.showToast("Analytics refreshed");
        });

        document.getElementById("refreshAuditBtn").addEventListener("click", async () => {
            await this.vm.fetchAuditLogs();
            this.renderAuditLogs();
            this.showToast("Audit polled");
        });

        const checkMeshBtn = document.getElementById("checkMeshBtn");
        if (checkMeshBtn) {
            checkMeshBtn.addEventListener("click", async () => {
                checkMeshBtn.disabled = true;
                const prevHtml = checkMeshBtn.innerHTML;
                checkMeshBtn.innerHTML = `<span class="mono">Probing 12 nodes...</span>`;
                try {
                    await this.renderMesh(true);
                } catch (err) {
                    console.error("Cluster probe error:", err);
                    this.showToast("Cluster probe error: " + err.message);
                } finally {
                    checkMeshBtn.disabled = false;
                }
            });
        }

        // Auto-fill Helpers (clean, unobtrusive)
        document.getElementById("fillDemoAddress").addEventListener("click", () => {
            document.getElementById("shipAddress").value = "Str. Studenților 9/7, Chișinău";
            this.showToast("Filled demo delivery address");
        });

        document.getElementById("fillDemoCard").addEventListener("click", () => {
            document.getElementById("cardNumber").value = "4532 8901 2345 9876";
            document.getElementById("cardExp").value = "12/28";
            document.getElementById("cardCvv").value = "777";
            this.showToast("Filled test sandbox card");
        });

        // Support ticket
        document.getElementById("submitTicketBtn").addEventListener("click", async () => {
            const sub = document.getElementById("ticketSubject").value.trim();
            const prio = document.getElementById("ticketPriority").value;
            const msg = document.getElementById("ticketMessage").value.trim();
            if (!sub || !msg) {
                alert("Please provide both subject and message");
                return;
            }
            try {
                const ok = await this.vm.createTicket(sub, prio, msg);
                if (ok) {
                    document.getElementById("ticketSubject").value = "";
                    document.getElementById("ticketMessage").value = "";
                    this.renderSupport();
                    this.showToast("Inquiry submitted");
                }
            } catch (e) {
                if (e.message === "AUTH_REQUIRED") this.openAuthModal();
            }
        });

        // Review Modal
        document.getElementById("closeReviewModal").addEventListener("click", () => {
            document.getElementById("reviewModal").classList.remove("active");
        });

        document.getElementById("submitReviewBtn").addEventListener("click", async () => {
            const rating = document.getElementById("newReviewRating").value;
            const comment = document.getElementById("newReviewComment").value.trim();
            if (!comment) return;
            try {
                const ok = await this.vm.submitReview(this.vm.model.selectedProductId, rating, comment);
                if (ok) {
                    document.getElementById("newReviewComment").value = "";
                    document.getElementById("reviewModal").classList.remove("active");
                    this.showToast("Review submitted");
                    await this.vm.searchProducts();
                    this.renderProducts();
                }
            } catch (e) {
                if (e.message === "AUTH_REQUIRED") this.openAuthModal();
            }
        });

        // Auth Modal
        document.getElementById("closeAuthModal").addEventListener("click", () => {
            document.getElementById("authModal").classList.remove("active");
        });

        document.getElementById("tabBtnLogin").addEventListener("click", () => {
            document.getElementById("tabBtnLogin").classList.add("active");
            document.getElementById("tabBtnRegister").classList.remove("active");
            document.getElementById("authLoginForm").style.display = "block";
            document.getElementById("authRegisterForm").style.display = "none";
        });

        document.getElementById("tabBtnRegister").addEventListener("click", () => {
            document.getElementById("tabBtnRegister").classList.add("active");
            document.getElementById("tabBtnLogin").classList.remove("active");
            document.getElementById("authLoginForm").style.display = "none";
            document.getElementById("authRegisterForm").style.display = "block";
        });

        document.getElementById("doLoginBtn").addEventListener("click", async () => {
            const email = document.getElementById("loginEmail").value.trim();
            const pass = document.getElementById("loginPassword").value.trim();
            try {
                const user = await this.vm.login(email, pass);
                document.getElementById("authModal").classList.remove("active");
                this.renderAuthArea();
                this.renderCart();
                this.renderOrders();
                this.showToast(`Signed in: ${user.full_name}`);
            } catch (err) {
                alert(err.message);
            }
        });

        document.getElementById("doRegisterBtn").addEventListener("click", async () => {
            const name = document.getElementById("regFullName").value.trim();
            const uname = document.getElementById("regUsername").value.trim();
            const email = document.getElementById("regEmail").value.trim();
            const pass = document.getElementById("regPassword").value.trim();
            if (!name || !email || !pass) {
                alert("Required fields missing");
                return;
            }
            try {
                const user = await this.vm.register(name, uname, email, pass);
                document.getElementById("authModal").classList.remove("active");
                this.renderAuthArea();
                this.renderCart();
                this.showToast(`Account created: ${user.full_name}`);
            } catch (err) {
                alert(err.message);
            }
        });

        // Quick demo switcher
        document.getElementById("quickLoginStudent").addEventListener("click", async () => {
            document.getElementById("loginEmail").value = "customer@cloudmart.io";
            document.getElementById("loginPassword").value = "customer123";
            const user = await this.vm.login("customer@cloudmart.io", "customer123");
            document.getElementById("authModal").classList.remove("active");
            this.renderAuthArea();
            this.renderCart();
            this.renderOrders();
            this.showToast(`Signed in: ${user.full_name} (Customer)`);
        });

        document.getElementById("quickLoginAdmin").addEventListener("click", async () => {
            document.getElementById("loginEmail").value = "admin@cloudmart.io";
            document.getElementById("loginPassword").value = "admin123";
            const user = await this.vm.login("admin@cloudmart.io", "admin123");
            document.getElementById("authModal").classList.remove("active");
            this.renderAuthArea();
            this.renderCart();
            this.renderOrders();
            this.showToast(`Signed in: ${user.full_name} (Admin)`);
        });

        // Global click to close dropdown
        document.addEventListener("click", (e) => {
            const menu = document.querySelector(".profile-menu");
            const chip = document.querySelector(".profile-chip");
            if (menu && !menu.contains(e.target) && chip && !chip.contains(e.target)) {
                menu.classList.remove("open");
            }
        });
    }

    openAuthModal() {
        document.getElementById("authModal").classList.add("active");
    }

    renderAuthArea() {
        const slot = document.getElementById("authArea");
        slot.innerHTML = "";

        const user = this.vm.model.currentUser;
        if (!user) {
            const btn = document.createElement("button");
            btn.className = "btn btn-secondary btn-sm";
            btn.textContent = "Sign In";
            btn.addEventListener("click", () => this.openAuthModal());
            slot.appendChild(btn);
        } else {
            const initials = user.full_name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
            const chip = document.createElement("div");
            chip.className = "profile-chip";
            chip.innerHTML = `
                <div class="avatar-initials">${initials}</div>
                <span class="profile-name">${user.full_name}</span>
            `;

            const menu = document.createElement("div");
            menu.className = "profile-menu";
            menu.innerHTML = `
                <div class="menu-info">
                    <div class="menu-name">${user.full_name}</div>
                    <div class="menu-email">${user.email}</div>
                </div>
                <button class="menu-action" id="switchAccBtn">Switch Account</button>
                <button class="menu-action danger" id="logoutBtn">Sign Out</button>
            `;

            chip.addEventListener("click", () => menu.classList.toggle("open"));

            menu.querySelector("#switchAccBtn").addEventListener("click", () => {
                menu.classList.remove("open");
                this.openAuthModal();
            });

            menu.querySelector("#logoutBtn").addEventListener("click", () => {
                this.vm.logout();
                this.renderAuthArea();
                this.renderCart();
                this.renderOrders();
                this.showToast("Signed out");
            });

            slot.appendChild(chip);
            slot.appendChild(menu);
        }
    }

    async handleSearch() {
        const q = document.getElementById("searchInput").value;
        const cat = document.getElementById("categoryFilter").value;
        const sort = document.getElementById("sortFilter").value;
        const stat = await this.vm.searchProducts(q, cat, sort);

        const latEl = document.getElementById("telemetryLatency");
        latEl.textContent = `${stat.latency}ms`;
        latEl.style.color = stat.cacheHeader === "HIT" ? "#10b981" : "#06b6d4";

        this.renderProducts();
    }

    async handleCheckout() {
        const addr = document.getElementById("shipAddress").value.trim();
        const card = document.getElementById("cardNumber").value.trim();
        const exp = document.getElementById("cardExp").value.trim();
        const cvv = document.getElementById("cardCvv").value.trim();

        if (!addr || !card) {
            alert("Please enter delivery address and card details (or use Auto-fill).");
            return;
        }

        let expMonth = "12";
        let expYear = "28";
        if (exp.includes("/")) {
            const parts = exp.split("/");
            expMonth = parts[0].trim() || "12";
            expYear = parts[1].trim() || "28";
        } else if (exp.length >= 4) {
            expMonth = exp.slice(0, 2);
            expYear = exp.slice(2, 4);
        }

        try {
            const order = await this.vm.checkout(addr, {
                cardNumber: card,
                cardCvv: cvv,
                expMonth,
                expYear
            });
            this.showToast(`Order #${order.id} placed`);
            this.renderCart();
            document.querySelector('[data-tab="orders"]').click();
        } catch (err) {
            if (err.message === "AUTH_REQUIRED") {
                this.openAuthModal();
                this.showToast("Sign in to complete order");
            } else {
                alert(err.message);
            }
        }
    }

    renderCategories() {
        const select = document.getElementById("categoryFilter");
        select.innerHTML = '<option value="">All Categories</option>';
        this.vm.model.categories.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c;
            opt.textContent = c;
            select.appendChild(opt);
        });
    }

    renderProducts() {
        const grid = document.getElementById("productsGrid");
        grid.innerHTML = "";

        if (this.vm.model.products.length === 0) {
            grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: #52525b; padding: 40px;">No hardware found.</div>`;
            return;
        }

        this.vm.model.products.forEach(p => {
            const card = document.createElement("div");
            card.className = "hardware-card";
            card.innerHTML = `
                <img src="${p.image_url}" alt="${p.title}" class="card-thumb" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500';">
                <div class="card-body">
                    <div class="card-meta-row">
                        <span class="cat-label">${p.category}</span>
                        <span class="star-rating rev-click" data-id="${p.id}">⭐ ${p.rating}</span>
                    </div>
                    <div class="card-title">${p.title}</div>
                    <div class="card-desc">${p.description}</div>
                    <div class="card-tags">
                        ${p.tags.map(t => `<span class="tag-badge">#${t}</span>`).join("")}
                    </div>
                    <div class="card-foot">
                        <div class="price-tag">$${p.price.toFixed(2)}</div>
                        <button class="btn btn-secondary btn-sm add-cart-btn" data-id="${p.id}">
                            + Add
                        </button>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });

        grid.querySelectorAll(".add-cart-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const prod = this.vm.model.products.find(p => p.id === btn.dataset.id);
                if (prod) {
                    await this.vm.addToCart(prod);
                    this.renderCartCount();
                    this.showToast(`Added to cart: ${prod.title}`);
                }
            });
        });

        grid.querySelectorAll(".rev-click").forEach(el => {
            el.addEventListener("click", () => {
                const prod = this.vm.model.products.find(p => p.id === el.dataset.id);
                if (prod) this.openReviewModal(prod);
            });
        });
    }

    async openReviewModal(product) {
        document.getElementById("modalProductTitle").textContent = `${product.title} Reviews`;
        document.getElementById("reviewModal").classList.add("active");

        const { reviews, stats } = await this.vm.fetchProductReviews(product.id);
        const statsEl = document.getElementById("modalRatingStats");
        if (stats) {
            statsEl.innerHTML = `
                <div style="font-size: 1.5rem; font-weight: 700; color: #f59e0b;" class="mono">⭐ ${stats.average_rating} / 5.0</div>
                <div style="color: #8a8a93; font-size: 0.75rem;">Based on ${stats.total_reviews} reviews</div>
            `;
        }

        const listEl = document.getElementById("modalReviewsList");
        listEl.innerHTML = "";
        if (reviews.length === 0) {
            listEl.innerHTML = `<p style="color: #52525b; font-size: 0.8rem; padding: 10px 0;">No reviews yet.</p>`;
        } else {
            reviews.forEach(r => {
                const el = document.createElement("div");
                el.style.cssText = "padding: 8px 0; border-bottom: 1px solid #1e1e24;";
                el.innerHTML = `
                    <div style="display: flex; justify-content: space-between; font-size: 0.8rem;">
                        <strong>${r.user_name}</strong>
                        <span style="color: #f59e0b;">${"⭐".repeat(r.rating)}</span>
                    </div>
                    <div style="color: #8a8a93; font-size: 0.8rem; margin-top: 2px;">${r.comment}</div>
                `;
                listEl.appendChild(el);
            });
        }
    }

    renderRecommendations() {
        const grid = document.getElementById("recommendationsGrid");
        grid.innerHTML = "";
        this.vm.model.recommendations.forEach(r => {
            const el = document.createElement("div");
            el.className = "rec-unit";
            el.innerHTML = `
                <img src="${r.image_url}" class="rec-img" onerror="this.src='https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=300';">
                <div class="rec-info">
                    <div class="rec-title">${r.title}</div>
                    <div class="rec-reason">${r.reason}</div>
                    <div class="rec-price mono">$${r.price.toFixed(2)}</div>
                </div>
            `;
            grid.appendChild(el);
        });
    }

    renderCartCount() {
        document.getElementById("cartCount").textContent = this.vm.model.cart.items_count || 0;
    }

    renderCart() {
        this.renderCartCount();
        const container = document.getElementById("cartItemsContainer");
        container.innerHTML = "";

        const items = this.vm.model.cart.items || [];
        if (items.length === 0) {
            container.innerHTML = `<div style="text-align: center; color: #52525b; padding: 40px;">Cart is empty.</div>`;
            document.getElementById("cartSubtotal").textContent = "$0.00";
            document.getElementById("cartTotal").textContent = "$0.00";
            return;
        }

        items.forEach(it => {
            const row = document.createElement("div");
            row.className = "cart-row-item";
            const productMatch = this.vm.model.products.find(p => p.id === it.product_id);
            const fallbackImg = "https://images.unsplash.com/photo-1587202372775-e229f172b9d7?w=500";
            const displayImg = it.image_url && it.image_url.trim() !== "" ? it.image_url : (productMatch?.image_url || fallbackImg);

            row.innerHTML = `
                <img src="${displayImg}" class="cart-img-box" onerror="this.onerror=null; this.src='${fallbackImg}';">
                <div class="cart-meta">
                    <div class="cart-title">${it.title}</div>
                    <div class="cart-unit-cost mono">$${it.price.toFixed(2)}</div>
                </div>
                <div class="counter-ctrl">
                    <button class="counter-btn" data-id="${it.product_id}" data-action="dec">-</button>
                    <span class="counter-val mono">${it.quantity}</span>
                    <button class="counter-btn" data-id="${it.product_id}" data-action="inc">+</button>
                </div>
                <div style="min-width: 75px; text-align: right;" class="mono font-semibold">
                    $${(it.price * it.quantity).toFixed(2)}
                </div>
            `;
            container.appendChild(row);
        });

        container.querySelectorAll(".counter-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const pid = btn.dataset.id;
                const act = btn.dataset.action;
                const it = items.find(i => i.product_id === pid);
                if (!it) return;

                if (act === "inc") {
                    await this.vm.updateCartQty(pid, it.quantity + 1);
                } else if (act === "dec") {
                    if (it.quantity > 1) {
                        await this.vm.updateCartQty(pid, it.quantity - 1);
                    } else {
                        await this.vm.removeFromCart(pid);
                    }
                }
                this.renderCart();
            });
        });

        const totalFormatted = `$${this.vm.model.cart.total_price.toFixed(2)}`;
        document.getElementById("cartSubtotal").textContent = totalFormatted;
        document.getElementById("cartTotal").textContent = totalFormatted;
    }

    renderOrders() {
        const container = document.getElementById("ordersContainer");
        container.innerHTML = "";

        if (!this.vm.model.currentUser) {
            container.innerHTML = `<div style="text-align: center; color: #52525b; padding: 40px;">Sign in to view orders.</div>`;
            return;
        }

        if (this.vm.model.orders.length === 0) {
            container.innerHTML = `<div style="text-align: center; color: #52525b; padding: 40px;">No placed orders.</div>`;
            return;
        }

        this.vm.model.orders.forEach(o => {
            const card = document.createElement("div");
            card.className = "order-box";
            const dateStr = new Date(o.created_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            card.innerHTML = `
                <div class="order-box-head">
                    <div>
                        <span class="mono font-semibold">${o.id}</span>
                        <span style="color: #52525b; font-size: 0.75rem; margin-left: 8px;">${dateStr}</span>
                    </div>
                    <span class="status-pill status-${o.status}">${o.status}</span>
                </div>
                <div style="font-size: 0.78rem; color: #8a8a93; margin-bottom: 8px;">
                    Destination: ${o.shipping_address}
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    ${o.items.map(it => `
                        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; background: #121215; padding: 6px 10px; border-radius: 4px;">
                            <span>${it.title} × ${it.quantity}</span>
                            <span class="mono">$${(it.price * it.quantity).toFixed(2)}</span>
                        </div>
                    `).join("")}
                </div>
                <div style="display: flex; justify-content: flex-end; align-items: center; margin-top: 10px; gap: 8px;">
                    <span style="color: #52525b; font-size: 0.78rem;">Total:</span>
                    <span style="font-size: 1rem; font-weight: 700; color: #10b981;" class="mono">$${o.total_amount.toFixed(2)}</span>
                </div>
            `;
            container.appendChild(card);
        });
    }

    renderAnalytics() {
        const a = this.vm.model.analytics;
        if (!a) return;

        document.getElementById("statRevenue").textContent = `$${a.total_revenue.toFixed(2)}`;
        document.getElementById("statOrders").textContent = a.total_orders;
        document.getElementById("statAov").textContent = `$${a.average_order_value.toFixed(2)}`;
        document.getElementById("statCatalog").textContent = a.total_catalog_products;

        const list = document.getElementById("topProductsList");
        list.innerHTML = "";
        if (!a.top_products || a.top_products.length === 0) {
            list.innerHTML = `<div style="color: #52525b; font-size: 0.8rem;">No sales recorded yet.</div>`;
            return;
        }

        a.top_products.forEach((tp, idx) => {
            const row = document.createElement("div");
            row.className = "sale-item";
            row.innerHTML = `
                <div>
                    <b>#${idx + 1}</b> ${tp.title}
                    <span style="color: #52525b; font-size: 0.75rem; margin-left: 6px;">(${tp.units_sold} units)</span>
                </div>
                <div class="mono font-semibold text-green">$${tp.revenue.toFixed(2)}</div>
            `;
            list.appendChild(row);
        });
    }

    renderSupport() {
        const list = document.getElementById("ticketsList");
        list.innerHTML = "";

        if (!this.vm.model.currentUser) {
            list.innerHTML = `<div style="color: #52525b; font-size: 0.8rem;">Sign in to view support threads.</div>`;
            return;
        }

        if (this.vm.model.tickets.length === 0) {
            list.innerHTML = `<div style="color: #52525b; font-size: 0.8rem;">No active inquiries.</div>`;
            return;
        }

        this.vm.model.tickets.forEach(t => {
            const box = document.createElement("div");
            box.className = "thread-entry";
            box.innerHTML = `
                <div class="thread-top">
                    <span>${t.subject}</span>
                    <span class="status-pill status-${t.status}">${t.status}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    ${t.messages.map(m => `
                        <div class="chat-row ${m.is_staff ? 'staff' : 'user'}">
                            <div style="font-size: 0.65rem; color: #8a8a93; font-weight: 600;">${m.sender_name}</div>
                            <div>${m.text}</div>
                        </div>
                    `).join("")}
                </div>
            `;
            list.appendChild(box);
        });
    }

    renderAuditLogs() {
        const tbody = document.getElementById("auditTableBody");
        tbody.innerHTML = "";

        if (this.vm.model.auditLogs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #52525b;">Empty audit ledger.</td></tr>`;
            return;
        }

        this.vm.model.auditLogs.forEach(entry => {
            const tr = document.createElement("tr");
            const dateStr = new Date(entry.timestamp * 1000).toLocaleTimeString();
            tr.innerHTML = `
                <td style="color: #52525b;">${dateStr}</td>
                <td><span style="color: #93c5fd;">${entry.service}</span></td>
                <td><span style="color: #6ee7b7;">${entry.action}</span></td>
                <td style="color: #8a8a93;">${entry.user_id}</td>
                <td style="color: #d4d4d8;">${entry.details}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    async renderMesh(probe = false) {
        const grid = document.getElementById("servicesMeshGrid");
        const summaryStrip = document.getElementById("meshProbeSummary");
        const checkBtn = document.getElementById("checkMeshBtn");

        let health = {};
        if (probe) {
            health = await this.vm.probeCluster();

            // Calculate aggregate metrics
            const statuses = Object.values(health);
            const upCount = statuses.filter(s => s.status === "UP").length;
            const validLatencies = statuses.filter(s => s.status === "UP").map(s => s.latency);
            const avgLat = validLatencies.length > 0 
                ? (validLatencies.reduce((a, b) => a + b, 0) / validLatencies.length).toFixed(1)
                : 0;
            const minLat = validLatencies.length > 0 ? Math.min(...validLatencies) : 0;
            const maxLat = validLatencies.length > 0 ? Math.max(...validLatencies) : 0;

            // 1. Update summary strip above diagram
            if (summaryStrip) {
                summaryStrip.style.display = "flex";
                const pssStatus = document.getElementById("pssClusterStatus");
                const pssAvg = document.getElementById("pssAvgLatency");
                const pssMinMax = document.getElementById("pssMinMaxLatency");
                if (pssStatus) {
                    pssStatus.textContent = `${upCount} / ${this.vm.model.servicesMesh.length} UP`;
                    pssStatus.className = `pss-val ${upCount === this.vm.model.servicesMesh.length ? 'text-green' : 'text-rose'}`;
                }
                if (pssAvg) pssAvg.textContent = `${avgLat} ms`;
                if (pssMinMax) pssMinMax.textContent = `${minLat}ms / ${maxLat}ms`;
            }

            // 2. Update Header Telemetry pill
            const telemLat = document.getElementById("telemetryLatency");
            if (telemLat) telemLat.textContent = `${avgLat}ms`;

            // 3. Update Button label
            if (checkBtn) {
                checkBtn.innerHTML = `✓ Probed (${avgLat}ms) &bull; Refresh`;
            }

            // 4. Update SVG Diagram nodes with live latency & highlight glow
            const svgMap = {
                catalog: "sn-catalog",
                search: "sn-search",
                recommendations: "sn-recs",
                reviews: "sn-reviews",
                cart: "sn-cart",
                orders: "sn-orders",
                payments: "sn-payments",
                auth: "sn-auth",
                audit: "sn-audit",
                notifications: "sn-notif",
                analytics: "sn-analytics",
                support: "sn-support"
            };

            Object.entries(svgMap).forEach(([svcId, svgNodeId]) => {
                const g = document.getElementById(svgNodeId);
                const h = health[svcId];
                if (g && h) {
                    const rect = g.querySelector("rect:first-child");
                    if (rect) {
                        const originalStroke = rect.getAttribute("stroke");
                        rect.style.transition = "stroke 0.3s ease, stroke-width 0.3s ease";
                        rect.setAttribute("stroke", h.status === "UP" ? "#10b981" : "#f43f5e");
                        rect.setAttribute("stroke-width", "2");
                        setTimeout(() => {
                            rect.setAttribute("stroke", originalStroke);
                            rect.setAttribute("stroke-width", "1.3");
                        }, 2500);
                    }
                    const texts = g.querySelectorAll("text");
                    texts.forEach(t => {
                        if (t.textContent.trim().startsWith(":80")) {
                            const port = t.textContent.trim().split(" ")[0].replace(/[^0-9]/g, "");
                            t.textContent = `:${port} (${h.latency}ms)`;
                        }
                    });
                }
            });

            // 5. Toast notification
            this.showToast(`Probed 12 nodes: ${upCount}/12 UP (avg ${avgLat}ms)`);
        }

        if (!grid) return;
        grid.innerHTML = "";

        this.vm.model.servicesMesh.forEach(svc => {
            const card = document.createElement("div");
            card.className = "node-box" + (probe ? " node-probed" : "");
            const h = health[svc.id] || (probe ? { status: "DOWN", latency: 0 } : { status: "ONLINE", latency: "READY" });
            const isDown = h.status === "DOWN";
            const isReady = h.latency === "READY";

            const badgeBg = isDown ? 'rgba(244,63,94,0.15)' : (isReady ? 'rgba(148,163,184,0.15)' : 'rgba(16,185,129,0.15)');
            const badgeColor = isDown ? '#f43f5e' : (isReady ? '#94a3b8' : '#6ee7b7');
            const latencyText = isReady ? 'READY' : `${h.latency}ms`;

            card.innerHTML = `
                <div class="node-box-head">
                    <span class="node-name">${svc.name}</span>
                    <span class="node-chip" style="background: ${badgeBg}; color: ${badgeColor};">
                        ${h.status} (${latencyText})
                    </span>
                </div>
                <div class="node-info-text">${svc.desc}</div>
                <div class="node-tags-row">
                    <span class="node-tag-pill mono text-cyan">:${svc.port}</span>
                    <span class="node-tag-pill mono">${svc.pattern}</span>
                    <span class="node-tag-pill mono" style="color: #94a3b8;">${svc.db}</span>
                </div>
                <div class="node-deps-text mono">${svc.deps}</div>
                <a href="/docs/${svc.id}" target="_blank" class="node-swagger-link">
                    OpenAPI Docs &rarr;
                </a>
            `;
            grid.appendChild(card);
        });
    }

    startTrafficStream() {
        this.stopTrafficStream();
        this.pollTraffic();
        this.trafficTimer = setInterval(() => this.pollTraffic(), 1200);
    }

    stopTrafficStream() {
        if (this.trafficTimer) {
            clearInterval(this.trafficTimer);
            this.trafficTimer = null;
        }
    }

    async pollTraffic() {
        if (this.trafficPaused) return;
        const logs = await this.vm.fetchTrafficLogs();
        if (Array.isArray(logs)) {
            this.trafficLogs = logs;
            this.updateTrafficStats();
            this.renderTraffic();
        }
    }

    updateTrafficStats() {
        const count = this.trafficLogs.length;
        const countEl = document.getElementById("trafficCount");
        if (countEl) countEl.textContent = count;

        if (count > 0) {
            const sumLatency = this.trafficLogs.reduce((acc, it) => acc + (it.latency_ms || 0), 0);
            const avg = (sumLatency / count).toFixed(1);
            const avgEl = document.getElementById("trafficAvgLatency");
            if (avgEl) avgEl.textContent = `${avg}ms`;

            const telemetryLatency = document.getElementById("telemetryLatency");
            if (telemetryLatency) telemetryLatency.textContent = `${avg}ms`;

            const cacheHits = this.trafficLogs.filter(it => it.cache === "HIT").length;
            const cacheHitsEl = document.getElementById("trafficCacheHits");
            if (cacheHitsEl) cacheHitsEl.textContent = cacheHits;
        }
    }

    renderTraffic() {
        const container = document.getElementById("trafficLogsList");
        if (!container) return;

        const filterTerm = (document.getElementById("trafficFilterInput")?.value || "").toLowerCase().trim();
        const methodFilter = document.getElementById("trafficMethodFilter")?.value || "";

        let items = [...this.trafficLogs];

        if (methodFilter) {
            items = items.filter(it => it.method === methodFilter);
        }

        if (filterTerm) {
            items = items.filter(it =>
                (it.path && it.path.toLowerCase().includes(filterTerm)) ||
                (it.service && it.service.toLowerCase().includes(filterTerm)) ||
                (it.hop && it.hop.toLowerCase().includes(filterTerm)) ||
                (it.target && it.target.toLowerCase().includes(filterTerm))
            );
        }

        if (items.length === 0) {
            container.innerHTML = `
                <div style="padding: 36px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                    No telemetry captured yet. Perform actions across CloudMart (search, browse, cart) to inspect live hops.
                </div>
            `;
            return;
        }

        // Newest on top
        items.reverse();

        container.innerHTML = items.map(it => {
            const isExpanded = this.expandedLogIds.has(it.id);
            const statusClass = it.status >= 500 ? "status-5xx" : (it.status >= 400 ? "status-4xx" : "status-2xx");
            const cacheHtml = it.cache === "HIT"
                ? `<span class="traffic-cache-tag">CACHE HIT</span>`
                : (it.cache === "MISS" ? `<span class="traffic-cache-tag miss">CACHE MISS</span>` : ``);

            const bodyPreviewHtml = it.body_preview ? `
                <div style="margin-top: 4px; font-weight: 600; color: #71717a;">Payload:</div>
                <div style="color: #cbd5e1;">${this.escapeHtml(it.body_preview)}</div>
            ` : `<div style="color: #71717a;">No payload body</div>`;

            return `
                <div class="traffic-item ${isExpanded ? 'expanded' : ''}" data-log-id="${it.id}">
                    <div class="traffic-row-main">
                        <div class="traffic-left">
                            <span class="traffic-time">${it.time_str || ''}</span>
                            <span class="method-tag method-${it.method}">${it.method}</span>
                            <span class="traffic-path">${it.path}</span>
                        </div>
                        <div class="traffic-right">
                            ${cacheHtml}
                            <span class="traffic-status ${statusClass}">${it.status}</span>
                            <span class="traffic-latency">${it.latency_ms}ms</span>
                        </div>
                    </div>
                    <div class="traffic-hop-row">
                        <span class="traffic-hop-pill">Client</span>
                        <span class="traffic-hop-arrow">&rarr;</span>
                        <span class="traffic-hop-pill">Gateway :80</span>
                        <span class="traffic-hop-arrow">&rarr;</span>
                        <span class="traffic-hop-pill">${it.service}-service</span>
                        <span class="traffic-hop-arrow">&rarr;</span>
                        <span style="color: #71717a;">${it.target}</span>
                    </div>
                    <div class="traffic-payload-drawer">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span style="color: #60a5fa;">Upstream URL:</span>
                            <span style="color: #71717a;">Trace ID: ${it.id}</span>
                        </div>
                        <div style="color: #e2e8f0; margin-bottom: 6px;">${it.target}</div>
                        ${bodyPreviewHtml}
                    </div>
                </div>
            `;
        }).join("");

        // Attach click to toggle expand
        container.querySelectorAll(".traffic-item").forEach(el => {
            el.addEventListener("click", () => {
                const logId = el.dataset.logId;
                if (this.expandedLogIds.has(logId)) {
                    this.expandedLogIds.delete(logId);
                    el.classList.remove("expanded");
                } else {
                    this.expandedLogIds.add(logId);
                    el.classList.add("expanded");
                }
            });
        });
    }

    escapeHtml(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
}

// ==========================================
// 4. BOOTSTRAP
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
    const model = new StoreModel();
    const vm = new StoreViewModel(model);
    const view = new StoreView(vm);

    await vm.init();
    view.renderAuthArea();
    view.renderCategories();
    view.renderProducts();
    view.renderCart();
    view.renderRecommendations();
    view.renderOrders();
    view.renderAnalytics();
    view.renderSupport();
    view.renderAuditLogs();
    view.renderMesh();
});
