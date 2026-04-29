document.addEventListener("DOMContentLoaded", function () {
    const paymentMethod = document.getElementById("paymentMethod");
    const paymentSections = document.querySelectorAll(".payment-section[data-payment]");
    const paymentInputs = document.querySelectorAll(".payment-input[data-payment-required]");
    const themeToggle = document.getElementById("themeToggle");

    function togglePaymentMethodDetails() {
        if (!paymentMethod) {
            return;
        }

        const selected = paymentMethod.value;

        paymentSections.forEach((section) => {
            const sectionMethod = section.getAttribute("data-payment");
            section.classList.toggle("d-none", sectionMethod !== selected);
        });

        paymentInputs.forEach((input) => {
            const inputMethod = input.getAttribute("data-payment-required");
            const isSelected = inputMethod === selected;

            if (input.type === "checkbox") {
                if (!isSelected) {
                    input.checked = false;
                }
            } else if (!isSelected) {
                input.value = "";
            }

            input.required = isSelected;
        });
    }

    function initTheme() {
        const storedTheme = localStorage.getItem("foodflux-theme") || "light";
        document.body.setAttribute("data-theme", storedTheme);
        updateThemeIcon(storedTheme);
    }

    function updateThemeIcon(theme) {
        if (!themeToggle) {
            return;
        }
        const icon = themeToggle.querySelector("i");
        if (!icon) {
            return;
        }
        icon.className = theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
    }

    function toggleTheme() {
        const currentTheme = document.body.getAttribute("data-theme") || "light";
        const nextTheme = currentTheme === "dark" ? "light" : "dark";
        document.body.setAttribute("data-theme", nextTheme);
        localStorage.setItem("foodflux-theme", nextTheme);
        updateThemeIcon(nextTheme);
    }

    function initScrollReveal() {
        const revealItems = document.querySelectorAll(".reveal-on-scroll");
        if (!revealItems.length) {
            return;
        }

        if (!("IntersectionObserver" in window)) {
            revealItems.forEach((item) => item.classList.add("revealed"));
            return;
        }

        const observer = new IntersectionObserver(
            (entries, obs) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("revealed");
                        obs.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.12 }
        );

        revealItems.forEach((item) => observer.observe(item));
    }

    function initWishlistButtons() {
        const buttons = document.querySelectorAll(".wishlist-btn[data-item]");
        if (!buttons.length) {
            return;
        }

        const storeKey = "foodflux-wishlist";
        const saved = JSON.parse(localStorage.getItem(storeKey) || "[]");
        const wishlist = new Set(saved);

        function syncIcon(button, active) {
            const icon = button.querySelector("i");
            button.classList.toggle("active", active);
            if (icon) {
                icon.className = active ? "bi bi-heart-fill" : "bi bi-heart";
            }
        }

        buttons.forEach((button) => {
            const itemId = button.getAttribute("data-item");
            syncIcon(button, wishlist.has(itemId));

            button.addEventListener("click", function () {
                if (wishlist.has(itemId)) {
                    wishlist.delete(itemId);
                    syncIcon(button, false);
                } else {
                    wishlist.add(itemId);
                    syncIcon(button, true);
                }
                localStorage.setItem(storeKey, JSON.stringify(Array.from(wishlist)));
            });
        });
    }

    function formatCurrency(amount) {
        return `₹${Number(amount || 0).toFixed(2)}`;
    }

    function postJson(url, payload) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify(payload || {}),
        }).then(async (response) => {
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.error || data.message || "Request failed.");
            }
            return data;
        });
    }

    function syncCartState(payload) {
        const count = Number(payload && payload.count ? payload.count : 0);
        const total = Number(payload && payload.total ? payload.total : 0);
        const items = Array.isArray(payload && payload.items) ? payload.items : [];

        const cartBadges = document.querySelectorAll(".cart-badge");
        cartBadges.forEach((badge) => {
            badge.textContent = String(count);
        });

        const floatingBar = document.getElementById("floatingCartBar");
        const summary = document.getElementById("floatingCartSummary");
        const drawerTotal = document.getElementById("cartDrawerTotal");
        const drawerItems = document.getElementById("cartDrawerItems");
        const drawerEmpty = document.getElementById("cartDrawerEmpty");

        if (floatingBar) {
            floatingBar.classList.toggle("d-none", count < 1);
        }
        if (summary) {
            summary.textContent = `${count} item${count === 1 ? "" : "s"} • ${formatCurrency(total)}`;
        }
        if (drawerTotal) {
            drawerTotal.textContent = formatCurrency(total);
        }

        if (drawerItems) {
            if (!items.length) {
                drawerItems.innerHTML = "";
                if (drawerEmpty) {
                    drawerEmpty.classList.remove("d-none");
                }
            } else {
                if (drawerEmpty) {
                    drawerEmpty.classList.add("d-none");
                }
                drawerItems.innerHTML = items
                    .map((item) => {
                        const imageUrl = item.image && item.image.startsWith("http")
                            ? item.image
                            : `/static/${item.image}`;
                        return `
                            <div class="cart-drawer-item" data-food-id="${item.food_id}">
                                <img src="${imageUrl}" alt="${item.name}" class="cart-drawer-item__image" onerror="this.onerror=null;this.src='/static/images/hero.svg';" />
                                <div class="cart-drawer-item__body">
                                    <div class="d-flex justify-content-between gap-2 align-items-start">
                                        <div>
                                            <div class="cart-drawer-item__title">${item.name}</div>
                                            <div class="cart-drawer-item__meta">${formatCurrency(item.price)} each</div>
                                        </div>
                                        <button type="button" class="btn btn-link text-danger p-0 js-cart-remove" data-food-id="${item.food_id}">Remove</button>
                                    </div>
                                    <div class="d-flex justify-content-between align-items-center mt-3">
                                        <div class="qty-stepper qty-stepper--compact">
                                            <button type="button" class="qty-btn js-cart-qty-btn" data-action="minus" data-food-id="${item.food_id}">-</button>
                                            <input type="number" class="form-control form-control-sm qty-input js-cart-qty-input" min="1" max="99" value="${item.qty}" data-food-id="${item.food_id}" />
                                            <button type="button" class="qty-btn js-cart-qty-btn" data-action="plus" data-food-id="${item.food_id}">+</button>
                                        </div>
                                        <strong>${formatCurrency(item.subtotal)}</strong>
                                    </div>
                                </div>
                            </div>
                        `;
                    })
                    .join("");
            }
        }
    }

    function fetchCartState() {
        const endpoint = document.body.getAttribute("data-cart-state-endpoint");
        if (!endpoint) {
            return Promise.resolve();
        }

        return fetch(endpoint, {
            method: "GET",
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Cart state fetch failed");
                }
                return response.json();
            })
            .then((payload) => {
                if (payload && payload.ok) {
                    syncCartState(payload);
                }
            })
            .catch(function () {
                // Ignore transient cart sync errors.
            });
    }

    function bindCartActions() {
        document.addEventListener("click", function (event) {
            const addLink = event.target.closest(".js-add-to-cart");
            if (addLink) {
                event.preventDefault();
                const url = addLink.getAttribute("data-cart-add-url") || addLink.getAttribute("href");
                if (!url) {
                    return;
                }
                fetch(url, {
                    method: "GET",
                    credentials: "same-origin",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                })
                    .then((response) => response.json())
                    .then((payload) => {
                        if (payload && payload.ok) {
                            syncCartState(payload);
                            showLiveToast("Cart updated", payload.message || "Item added to cart.", "alert-success");
                        }
                    })
                    .catch(function () {
                        window.location.href = url;
                    });
                return;
            }

            const qtyButton = event.target.closest(".js-cart-qty-btn");
            if (qtyButton) {
                event.preventDefault();
                const foodId = qtyButton.getAttribute("data-food-id");
                const action = qtyButton.getAttribute("data-action");
                const row = qtyButton.closest(".cart-drawer-item");
                const input = row ? row.querySelector(".js-cart-qty-input") : null;
                const currentQty = input ? parseInt(input.value || "1", 10) : 1;
                const nextQty = action === "minus" ? currentQty - 1 : currentQty + 1;

                postJson("/api/cart/update", { food_id: foodId, quantity: nextQty })
                    .then((payload) => {
                        syncCartState(payload);
                    })
                    .catch(function (error) {
                        showLiveToast("Cart error", error.message, "alert-danger");
                    });
                return;
            }

            const removeButton = event.target.closest(".js-cart-remove");
            if (removeButton) {
                event.preventDefault();
                const foodId = removeButton.getAttribute("data-food-id");
                postJson("/api/cart/update", { food_id: foodId, quantity: 0 })
                    .then((payload) => {
                        syncCartState(payload);
                    })
                    .catch(function (error) {
                        showLiveToast("Cart error", error.message, "alert-danger");
                    });
            }
        });

        document.addEventListener("input", function (event) {
            const qtyInput = event.target.closest(".js-cart-qty-input");
            if (!qtyInput) {
                return;
            }
            const foodId = qtyInput.getAttribute("data-food-id");
            const quantity = parseInt(qtyInput.value || "1", 10);
            if (Number.isNaN(quantity)) {
                return;
            }
            postJson("/api/cart/update", { food_id: foodId, quantity })
                .then((payload) => {
                    syncCartState(payload);
                })
                .catch(function (error) {
                    showLiveToast("Cart error", error.message, "alert-danger");
                });
        });
    }

    function requestOtpForForm(form, requestButton) {
        const formData = new FormData(form);
        const purpose = (formData.get("purpose") || form.getAttribute("data-purpose") || "login").toString();
        const mobileNumber = (formData.get("mobile_number") || "").toString().trim();
        const role = (formData.get("role") || form.getAttribute("data-role") || "").toString().trim();
        const payload = { purpose, mobile_number: mobileNumber };

        if (role) {
            payload.role = role;
        }

        if (!mobileNumber) {
            showLiveToast("OTP request failed", "Enter a valid mobile number.", "alert-danger");
            return;
        }

        requestButton.disabled = true;
        postJson("/api/auth/otp/request", payload)
            .then((response) => {
                showLiveToast("OTP sent", response.message || "OTP generated successfully.", "alert-success");
                if (response.dev_otp) {
                    showLiveToast("Development OTP", `Use code ${response.dev_otp} while testing locally.`, "alert-info");
                    window.setTimeout(function () {
                        const otpField = form.querySelector('input[name="otp_code"]');
                        if (otpField) {
                            otpField.value = response.dev_otp;
                        }
                    }, 1200);
                }
            })
            .catch(function (error) {
                showLiveToast("OTP request failed", error.message, "alert-danger");
            })
            .finally(function () {
                window.setTimeout(function () {
                    requestButton.disabled = false;
                }, 30000);
            });
    }

    function submitMobileAuthForm(form) {
        const formData = new FormData(form);
        const purpose = (formData.get("purpose") || form.getAttribute("data-purpose") || "login").toString();
        const mobileNumber = (formData.get("mobile_number") || "").toString().trim();
        const otpCode = (formData.get("otp_code") || "").toString().trim();
        const role = (formData.get("role") || form.getAttribute("data-role") || "").toString().trim();
        const password = (formData.get("password") || "").toString();
        const fullName = (formData.get("full_name") || formData.get("name") || "").toString().trim();
        const nextUrl = (formData.get("next") || "").toString().trim();

        const sharedPayload = { purpose, mobile_number: mobileNumber };
        if (role) {
            sharedPayload.role = role;
        }
        if (nextUrl) {
            sharedPayload.next = nextUrl;
        }

        function verifyOtpIfNeeded() {
            if (!otpCode) {
                return Promise.resolve();
            }
            return postJson("/api/auth/otp/verify", { ...sharedPayload, otp_code: otpCode });
        }

        function finalizeRequest() {
            if (purpose === "register") {
                return postJson("/api/auth/mobile/register", {
                    full_name: fullName,
                    mobile_number: mobileNumber,
                    password,
                });
            }

            if (purpose === "staff_onboard") {
                return postJson("/api/admin/staff/onboard", {
                    name: fullName,
                    mobile_number: mobileNumber,
                    password,
                    role,
                });
            }

            if (purpose === "staff_login") {
                if (otpCode) {
                    return postJson("/api/auth/staff/mobile/login-otp", {
                        mobile_number: mobileNumber,
                        role,
                    });
                }
                return postJson("/api/auth/staff/mobile/login", {
                    mobile_number: mobileNumber,
                    password,
                    role,
                });
            }

            if (otpCode) {
                return postJson("/api/auth/mobile/login-otp", {
                    mobile_number: mobileNumber,
                    next: nextUrl,
                });
            }
            return postJson("/api/auth/mobile/login", {
                mobile_number: mobileNumber,
                password,
                next: nextUrl,
            });
        }

        if (!mobileNumber) {
            showLiveToast("Missing mobile number", "Enter a valid mobile number.", "alert-danger");
            return;
        }

        if (purpose === "staff_onboard" && !otpCode) {
            showLiveToast("OTP required", "Verify the mobile number before creating the staff account.", "alert-danger");
            return;
        }

        verifyOtpIfNeeded()
            .then(finalizeRequest)
            .then((response) => {
                if (response && response.message) {
                    showLiveToast("Success", response.message, "alert-success");
                }
                if (response && response.redirect) {
                    window.location.href = response.redirect;
                    return;
                }
                if (purpose === "staff_onboard") {
                    form.reset();
                    fetchCartState();
                }
            })
            .catch(function (error) {
                showLiveToast("Request failed", error.message, "alert-danger");
            });
    }

    function initMobileAuthForms() {
        const forms = document.querySelectorAll(".js-mobile-auth-form");
        if (!forms.length) {
            return;
        }

        forms.forEach((form) => {
            const requestButton = form.querySelector(".js-request-otp");
            if (requestButton) {
                requestButton.addEventListener("click", function () {
                    requestOtpForForm(form, requestButton);
                });
            }

            form.addEventListener("submit", function (event) {
                event.preventDefault();
                submitMobileAuthForm(form);
            });
        });
    }

    function initQtySteppers() {
        const controls = document.querySelectorAll(".qty-stepper");
        controls.forEach((wrapper) => {
            const input = wrapper.querySelector(".qty-input");
            const buttons = wrapper.querySelectorAll(".qty-btn");
            if (!input || !buttons.length) {
                return;
            }

            buttons.forEach((button) => {
                button.addEventListener("click", function () {
                    const action = button.getAttribute("data-action");
                    const min = parseInt(input.getAttribute("min") || "1", 10);
                    const max = parseInt(input.getAttribute("max") || "99", 10);
                    let value = parseInt(input.value || "1", 10);
                    value = Number.isNaN(value) ? min : value;

                    if (action === "plus") {
                        value += 1;
                    }
                    if (action === "minus") {
                        value -= 1;
                    }

                    value = Math.max(min, Math.min(max, value));
                    input.value = value;
                });
            });
        });
    }

    function initEnhancedLoginForms() {
        const forms = document.querySelectorAll(".js-login-form");
        if (!forms.length) {
            return;
        }

        forms.forEach((form) => {
            const passwordInput = form.querySelector(".js-password-input");
            const toggleButton = form.querySelector(".js-password-toggle");
            const capsWarning = form.querySelector(".js-caps-warning");
            const submitButton = form.querySelector(".js-login-submit");
            const submitText = form.querySelector(".js-login-submit-text");
            const defaultSubmitText = submitText ? submitText.textContent : "Login";

            if (toggleButton && passwordInput) {
                toggleButton.addEventListener("click", function () {
                    const icon = toggleButton.querySelector("i");
                    const isPassword = passwordInput.type === "password";
                    passwordInput.type = isPassword ? "text" : "password";
                    toggleButton.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
                    if (icon) {
                        icon.className = isPassword ? "bi bi-eye-slash" : "bi bi-eye";
                    }
                });
            }

            if (passwordInput && capsWarning) {
                passwordInput.addEventListener("keyup", function (event) {
                    if (typeof event.getModifierState !== "function") {
                        return;
                    }
                    const capsActive = event.getModifierState("CapsLock");
                    capsWarning.classList.toggle("d-none", !capsActive);
                });

                passwordInput.addEventListener("blur", function () {
                    capsWarning.classList.add("d-none");
                });
            }

            form.addEventListener("submit", function () {
                if (submitButton) {
                    submitButton.disabled = true;
                }
                if (submitText) {
                    submitText.textContent = "Signing in...";
                }

                setTimeout(function () {
                    if (submitButton) {
                        submitButton.disabled = false;
                    }
                    if (submitText) {
                        submitText.textContent = defaultSubmitText;
                    }
                }, 9000);
            });
        });
    }

    function initRoutePrefetch() {
        const role = document.body.getAttribute("data-role") || "guest";
        if (role !== "guest" || typeof fetch !== "function") {
            return;
        }

        const routes = ["/login", "/register", "/manager/login", "/delivery/login"];
        const prefetch = function () {
            routes.forEach((route) => {
                fetch(route, {
                    method: "GET",
                    credentials: "same-origin",
                    headers: { "X-Requested-With": "prefetch" },
                }).catch(function () {
                    // Ignore prefetch errors; route loads normally when clicked.
                });
            });
        };

        if ("requestIdleCallback" in window) {
            window.requestIdleCallback(prefetch, { timeout: 1200 });
        } else {
            setTimeout(prefetch, 600);
        }
    }

    function statusBadgeClass(status) {
        if (status === "Delivered") {
            return "badge bg-success order-status-badge";
        }
        if (status === "On the Way" || status === "Picked Up") {
            return "badge bg-primary order-status-badge";
        }
        if (status === "Near Customer") {
            return "badge bg-warning text-dark order-status-badge";
        }
        if (status === "Order Accepted" || status === "Preparing Food" || status === "Ready for Pickup" || status === "Rider Assigned") {
            return "badge bg-info text-dark order-status-badge";
        }
        if (status === "Cancelled" || status === "Rejected") {
            return "badge bg-danger order-status-badge";
        }
        return "badge bg-warning text-dark order-status-badge";
    }

    function panelStatusLabel(status) {
        if (status === "Delivered") {
            return { text: "Completed", klass: "badge bg-success delivery-panel-badge" };
        }
        if (status === "On the Way" || status === "Picked Up") {
            return { text: "On Route", klass: "badge bg-primary delivery-panel-badge" };
        }
        if (status === "Near Customer") {
            return { text: "Near Customer", klass: "badge bg-warning text-dark delivery-panel-badge" };
        }
        if (status === "Ready for Pickup") {
            return { text: "Ready to Dispatch", klass: "badge bg-info text-dark delivery-panel-badge" };
        }
        if (status === "Rider Assigned") {
            return { text: "Rider Assigned", klass: "badge bg-info text-dark delivery-panel-badge" };
        }
        if (status === "Order Accepted") {
            return { text: "Accepted", klass: "badge bg-info text-dark delivery-panel-badge" };
        }
        return { text: "Preparing", klass: "badge bg-secondary delivery-panel-badge" };
    }

    function showLiveToast(title, message, styleClass = "alert-info") {
        const toast = document.createElement("div");
        toast.className = `alert ${styleClass}`;
        toast.style.position = "fixed";
        toast.style.top = "16px";
        toast.style.right = "16px";
        toast.style.width = "min(440px, calc(100% - 32px))";
        toast.style.zIndex = "10000";
        toast.style.boxShadow = "0 16px 30px rgba(15, 23, 42, 0.18)";
        toast.innerHTML = `<strong>${title}</strong><div>${message}</div>`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4500);
    }

    function updateRowByOrderId(tableId, payload, options = {}) {
        const table = document.getElementById(tableId);
        if (!table) {
            return;
        }

        const row = table.querySelector(`tr[data-order-id="${payload.id}"]`);
        if (!row) {
            return;
        }

        const statusBadge = row.querySelector(".order-status-badge");
        if (statusBadge) {
            statusBadge.className = statusBadgeClass(payload.status);
            statusBadge.textContent = payload.status;
        }

        const deliveryCell = row.querySelector(".delivery-person-cell");
        if (deliveryCell && payload.delivery_person) {
            deliveryCell.textContent = payload.delivery_person;
        }

        const panelBadge = row.querySelector(".delivery-panel-badge");
        if (panelBadge) {
            const panel = panelStatusLabel(payload.status);
            panelBadge.className = panel.klass;
            panelBadge.textContent = panel.text;
        }

        if (options.removeOnDelivered && payload.status === "Delivered") {
            row.remove();
        }
    }

    function renderManagerActions(order) {
        const actions = [];
        if (order.status === "Order Placed") {
            actions.push({ label: "Accept", status: "Order Accepted", klass: "btn-outline-success" });
            actions.push({ label: "Reject", status: "Rejected", klass: "btn-outline-danger" });
        } else if (order.status === "Order Accepted") {
            actions.push({ label: "Preparing", status: "Preparing Food", klass: "btn-outline-warning" });
            actions.push({ label: "Cancel", status: "Cancelled", klass: "btn-outline-danger" });
        } else if (order.status === "Preparing Food") {
            actions.push({ label: "Ready", status: "Ready for Pickup", klass: "btn-outline-info" });
            actions.push({ label: "Cancel", status: "Cancelled", klass: "btn-outline-danger" });
        }

        return actions.map((action) => `<a href="/admin/order/status/${order.id}/${encodeURIComponent(action.status)}" class="btn btn-sm ${action.klass}">${action.label}</a>`).join("");
    }

    function renderDeliveryActions(order) {
        const actions = [];
        if (order.status === "Ready for Pickup") {
            actions.push({ label: "Accept", status: "Accept", klass: "btn-outline-success" });
            actions.push({ label: "Reject", status: "Reject", klass: "btn-outline-danger" });
        } else if (order.status === "Rider Assigned") {
            actions.push({ label: "Picked", status: "Picked Up", klass: "btn-outline-info" });
        } else if (order.status === "Picked Up") {
            actions.push({ label: "On Way", status: "On the Way", klass: "btn-outline-primary" });
        } else if (order.status === "On the Way") {
            actions.push({ label: "Near", status: "Near Customer", klass: "btn-outline-warning" });
        } else if (order.status === "Near Customer") {
            actions.push({ label: "Done", status: "Delivered", klass: "btn-outline-success" });
        }

        return actions.map((action) => `<a href="/delivery/order/status/${order.id}/${encodeURIComponent(action.status)}" class="btn btn-sm ${action.klass}">${action.label}</a>`).join("");
    }

    function renderManagerOrderRow(order) {
        const status = order.status || "";
        const statusClass = statusBadgeClass(status);
        const deliveryPerson = order.delivery_person || "Not Assigned";
        const panel = panelStatusLabel(status);
        const actions = renderManagerActions(order);
        return `
            <tr data-order-id="${order.id}">
                <td>${order.id}</td>
                <td>${order.customer_name || "Guest"}<br><small>${order.customer_email || ""}</small></td>
                <td>₹${Number(order.total || 0).toFixed(2)}</td>
                <td>${order.payment || ""}</td>
                <td><span class="${statusClass}">${status}</span></td>
                <td class="delivery-person-cell">${deliveryPerson}</td>
                <td><span class="badge delivery-panel-badge ${panel.klass.replace("badge ", "")}">${panel.text}</span></td>
                <td>${order.address || ""}</td>
                <td>${order.phone || ""}</td>
                <td><div class="d-flex flex-wrap gap-1">${actions}</div></td>
            </tr>
        `;
    }

    function renderDeliveryOrderRow(order) {
        const status = order.status || "";
        const statusClass = statusBadgeClass(status);
        const actions = renderDeliveryActions(order);
        return `
            <tr data-order-id="${order.id}">
                <td>#${order.id}</td>
                <td>${order.customer_name || "Customer"}<br><small class="text-muted">${order.customer_email || ""}</small></td>
                <td><span class="${statusClass}">${status}</span></td>
                <td>${order.address || ""}</td>
                <td>${order.phone || ""}</td>
                <td><div class="d-flex flex-wrap gap-1">${actions}</div></td>
            </tr>
        `;
    }

    function renderCustomerOrders(orders) {
        const table = document.getElementById("customerOrdersTable");
        if (!table) {
            return;
        }
        const tbody = table.querySelector("tbody");
        if (!tbody) {
            return;
        }

        if (!orders || !orders.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No orders yet. Start by browsing the menu.</td></tr>';
            return;
        }

        tbody.innerHTML = orders.map((order) => `
            <tr data-order-id="${order.id}">
                <td>#${order.id}</td>
                <td><span class="${statusBadgeClass(order.status)}">${order.status}</span></td>
                <td class="delivery-person-cell">${order.delivery_person || "Assigning..."}</td>
                <td>₹${Number(order.total || 0).toFixed(2)}</td>
                <td>${order.created_at || ""}</td>
                <td><a href="/track_order/${order.id}" class="btn btn-sm btn-outline-primary">Track</a></td>
            </tr>
        `).join("");
        updateCustomerCounters();
    }

    function renderManagerOrders(orders) {
        const table = document.getElementById("managerOrdersTable");
        if (!table) {
            return;
        }
        const tbody = table.querySelector("tbody");
        if (!tbody) {
            return;
        }
        if (!orders || !orders.length) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted">No live orders right now.</td></tr>';
            return;
        }
        tbody.innerHTML = orders.map(renderManagerOrderRow).join("");
    }

    function renderManagerPanel(panelRows) {
        const body = document.getElementById("managerDeliveryPanelBody");
        if (!body) {
            return;
        }
        if (!panelRows || !panelRows.length) {
            body.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No delivery assignments yet.</td></tr>';
            return;
        }

        body.innerHTML = panelRows.map((row) => {
            const status = row.latest_status || "Idle";
            const badgeClass = status === "Delivered"
                ? "badge bg-success"
                : (status === "On the Way" || status === "Picked Up")
                    ? "badge bg-primary"
                    : (status === "Near Customer")
                        ? "badge bg-warning text-dark"
                        : (status === "Ready for Pickup" || status === "Order Accepted" || status === "Rider Assigned")
                            ? "badge bg-info text-dark"
                            : (status === "Cancelled" || status === "Rejected")
                                ? "badge bg-danger"
                                : "badge bg-secondary";
            return `
                <tr>
                    <td>${row.delivery_person || "-"}</td>
                        <td><span class="${badgeClass}">${status}</span></td>
                    <td>${row.active_orders || 0}</td>
                    <td>${row.delivered_orders || 0}</td>
                    <td>${row.assigned_orders || 0}</td>
                </tr>
            `;
        }).join("");
    }

    function renderDeliveryOrders(orders) {
        const table = document.getElementById("deliveryOrdersTable");
        if (!table) {
            return;
        }
        const tbody = table.querySelector("tbody");
        if (!tbody) {
            return;
        }
        if (!orders || !orders.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No orders assigned yet.</td></tr>';
            return;
        }
        tbody.innerHTML = orders.map(renderDeliveryOrderRow).join("");
        updateDeliveryCounters();
    }

    function updateLiveDashboard(payload) {
        if (!payload || !payload.kind) {
            return;
        }

        if (payload.kind === "customer_dashboard") {
            const summary = payload.summary || {};
            const totalEl = document.getElementById("customerTotalOrders");
            const activeEl = document.getElementById("customerActiveOrders");
            const deliveredEl = document.getElementById("customerDeliveredOrders");
            if (totalEl) totalEl.textContent = String(summary.total || 0);
            if (activeEl) activeEl.textContent = String(summary.active || 0);
            if (deliveredEl) deliveredEl.textContent = String(summary.delivered || 0);
            renderCustomerOrders(payload.orders || []);
        }

        if (payload.kind === "manager_dashboard") {
            const stats = payload.stats || {};
            const totalEl = document.querySelector("#managerOrderTotal, #orderTotal, #adminTotalOrders, .js-manager-total-orders");
            const activeEl = document.querySelector("#managerActiveOrders, #activeOrders, .js-manager-active-orders");
            const deliveredEl = document.querySelector("#managerDeliveredOrders, #deliveredOrders, .js-manager-delivered-orders");
            if (totalEl) totalEl.textContent = String(stats.total || 0);
            if (activeEl) activeEl.textContent = String(stats.active || 0);
            if (deliveredEl) deliveredEl.textContent = String(stats.delivered || 0);
            renderManagerPanel(payload.panel || []);
        }

        if (payload.kind === "manager_orders") {
            renderManagerOrders(payload.orders || []);
        }

        if (payload.kind === "delivery_dashboard") {
            const stats = payload.stats || {};
            const totalEl = document.getElementById("deliveryAssignedOrders");
            const acceptedEl = document.getElementById("deliveryAcceptedOrders");
            const activeEl = document.getElementById("deliveryActiveOrders");
            const doneEl = document.getElementById("deliveryDoneOrders");
            if (totalEl) totalEl.textContent = String(stats.total || 0);
            if (acceptedEl) acceptedEl.textContent = String(stats.accepted || 0);
            if (activeEl) activeEl.textContent = String(stats.active || 0);
            if (doneEl) doneEl.textContent = String(stats.delivered || 0);
            renderDeliveryOrders(payload.orders || []);
        }
    }

    function updateCustomerCounters() {
        const table = document.getElementById("customerOrdersTable");
        if (!table) {
            return;
        }

        const rows = table.querySelectorAll("tbody tr[data-order-id]");
        let total = 0;
        let delivered = 0;
        let active = 0;

        rows.forEach((row) => {
            const statusBadge = row.querySelector(".order-status-badge");
            const status = (statusBadge ? statusBadge.textContent : "").trim();
            total += 1;
            if (status === "Delivered") {
                delivered += 1;
            } else if (status !== "Cancelled" && status !== "Rejected") {
                active += 1;
            } else {
                // Cancelled/Rejected are excluded from active counter.
            }
        });

        const totalEl = document.getElementById("customerTotalOrders");
        const activeEl = document.getElementById("customerActiveOrders");
        const deliveredEl = document.getElementById("customerDeliveredOrders");

        if (totalEl) {
            totalEl.textContent = String(total);
        }
        if (activeEl) {
            activeEl.textContent = String(active);
        }
        if (deliveredEl) {
            deliveredEl.textContent = String(delivered);
        }
    }

    function updateDeliveryCounters() {
        const table = document.getElementById("deliveryOrdersTable");
        if (!table) {
            return;
        }

        const rows = table.querySelectorAll("tbody tr[data-order-id]");
        let total = 0;
        let accepted = 0;
        let delivered = 0;
        let active = 0;

        rows.forEach((row) => {
            const statusBadge = row.querySelector(".order-status-badge");
            const status = (statusBadge ? statusBadge.textContent : "").trim();
            total += 1;
            if (status !== "") {
                accepted += 1;
            }
            if (status === "Delivered") {
                delivered += 1;
            } else if (status !== "Cancelled" && status !== "Rejected") {
                active += 1;
            } else {
                // Cancelled/Rejected are excluded from active counter.
            }
        });

        const totalEl = document.getElementById("deliveryAssignedOrders");
        const acceptedEl = document.getElementById("deliveryAcceptedOrders");
        const activeEl = document.getElementById("deliveryActiveOrders");
        const doneEl = document.getElementById("deliveryDoneOrders");

        if (totalEl) {
            totalEl.textContent = String(total);
        }
        if (acceptedEl) {
            acceptedEl.textContent = String(accepted);
        }
        if (activeEl) {
            activeEl.textContent = String(active);
        }
        if (doneEl) {
            doneEl.textContent = String(delivered);
        }
    }

    function handleTrackOrderRealtime(payload) {
        const badge = document.getElementById("statusBadge");
        if (!badge) {
            return;
        }

        const orderId = parseInt(badge.getAttribute("data-order-id") || "0", 10);
        if (orderId !== payload.id) {
            return;
        }

        badge.className = statusBadgeClass(payload.status);
        badge.id = "statusBadge";
        badge.setAttribute("data-order-id", String(orderId));
        badge.textContent = payload.status;

        if (payload.status === "Delivered") {
            showLiveToast("Order Delivered", `Order #${payload.id} has been delivered.`, "alert-success");
        }
    }

    let liveRefreshLocked = false;

    function showLiveRefreshing() {
        if (liveRefreshLocked) {
            return;
        }
        liveRefreshLocked = true;
        const existing = document.getElementById("liveRefreshToast");
        if (existing) {
            return;
        }
        const toast = document.createElement("div");
        toast.id = "liveRefreshToast";
        toast.className = "alert alert-info";
        toast.style.position = "fixed";
        toast.style.bottom = "16px";
        toast.style.right = "16px";
        toast.style.zIndex = "10000";
        toast.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Refreshing live updates...';
        document.body.appendChild(toast);
    }

    function parseDateSafe(value) {
        if (!value) {
            return null;
        }
        const normalized = String(value).trim().replace(" ", "T");
        const parsed = new Date(normalized);
        if (Number.isNaN(parsed.getTime())) {
            return null;
        }
        return parsed;
    }

    function initDashboardPolling() {
        const watcher = document.querySelector(".js-live-watch");
        if (!watcher) {
            return;
        }

        const endpoint = watcher.getAttribute("data-live-endpoint");
        let currentToken = watcher.getAttribute("data-live-token") || "";
        if (!endpoint) {
            return;
        }

        setInterval(function () {
            fetch(endpoint, {
                method: "GET",
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then((response) => {
                    if (!response.ok) {
                        throw new Error("live fetch failed");
                    }
                    return response.json();
                })
                .then((payload) => {
                    if (!payload || typeof payload.token !== "string") {
                        return;
                    }
                    if (payload.token !== currentToken) {
                        updateLiveDashboard(payload);
                        showLiveRefreshing();
                    }
                    currentToken = payload.token;
                })
                .catch(function () {
                    // Ignore transient poll errors.
                });
        }, 5000);
    }

    function initTrackOrderPolling() {
        const watcher = document.querySelector(".js-track-live-watch");
        const badge = document.getElementById("statusBadge");
        if (!watcher || !badge) {
            return;
        }

        const endpoint = watcher.getAttribute("data-live-endpoint");
        const partnerEl = document.getElementById("trackDeliveryPartner");
        const tracker = document.getElementById("liveTracker");
        const phoneEl = document.getElementById("trackCustomerPhone");
        const timelineText = document.getElementById("riderLiveLocationText");
        let lastSignature = "";

        if (!endpoint) {
            return;
        }

        setInterval(function () {
            fetch(endpoint, {
                method: "GET",
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then((response) => {
                    if (!response.ok) {
                        throw new Error("track fetch failed");
                    }
                    return response.json();
                })
                .then((payload) => {
                    if (!payload || !payload.id) {
                        return;
                    }

                    const nextSignature = [
                        payload.status || "",
                        payload.delivery_person || "",
                        payload.auto_delivered_at || "",
                    ].join("|");

                    if (lastSignature === "") {
                        lastSignature = nextSignature;
                    }

                    badge.className = statusBadgeClass(payload.status);
                    badge.id = "statusBadge";
                    badge.setAttribute("data-order-id", String(payload.id));
                    badge.textContent = payload.status;

                    if (partnerEl) {
                        partnerEl.textContent = payload.delivery_person || "Assigning...";
                    }

                    const serviceRatingCard = document.getElementById("serviceRatingCard");
                    const itemRatingForms = document.querySelectorAll(".js-item-rating-form");
                    const showRatings = payload.status === "Delivered";
                    if (serviceRatingCard) {
                        serviceRatingCard.classList.toggle("d-none", !showRatings);
                    }
                    itemRatingForms.forEach((form) => {
                        form.classList.toggle("d-none", !showRatings);
                    });

                    if (phoneEl) {
                        phoneEl.textContent = payload.status === "Ready for Pickup" || payload.status === "Rider Assigned" || payload.status === "Picked Up" || payload.status === "On the Way" || payload.status === "Near Customer" || payload.status === "Delivered"
                            ? (payload.phone || phoneEl.textContent)
                            : "Hidden until order is Ready";
                    }

                    if (tracker) {
                        const steps = Array.from(tracker.querySelectorAll(".live-tracker__step"));
                        const currentIndex = ["Order Placed", "Order Accepted", "Preparing Food", "Ready for Pickup", "Picked Up", "On the Way", "Near Customer", "Delivered"].indexOf(payload.status);
                        steps.forEach((step, index) => {
                            const active = index <= currentIndex || (payload.status === "Rider Assigned" && step.getAttribute("data-step") === "Ready for Pickup");
                            step.classList.toggle("is-active", active);
                            const dot = step.querySelector(".live-tracker__dot");
                            if (dot) {
                                dot.textContent = active ? "✓" : "";
                            }
                        });
                    }

                    if (payload.rider_location && window.updateRiderMapMarker) {
                        window.updateRiderMapMarker(payload.rider_location.lat, payload.rider_location.lng);
                        if (timelineText) {
                            timelineText.textContent = `Rider location updated: ${payload.rider_location.lat.toFixed(5)}, ${payload.rider_location.lng.toFixed(5)}`;
                        }
                    }

                    if (nextSignature !== lastSignature) {
                        lastSignature = nextSignature;
                    }
                })
                .catch(function () {
                    // Ignore transient poll errors.
                });
        }, 4000);
    }

    function initDeliveryLocationSync() {
        const role = document.body.getAttribute("data-role");
        if (role !== "delivery_partner" || !navigator.geolocation) {
            return;
        }

        setInterval(function () {
            const candidateRows = document.querySelectorAll("#deliveryOrdersTable tr[data-order-id]");
            let activeRow = null;

            candidateRows.forEach((row) => {
                if (activeRow) {
                    return;
                }
                const badge = row.querySelector(".order-status-badge");
                const status = (badge ? badge.textContent : "").trim();
                if (["Rider Assigned", "Picked Up", "On the Way"].includes(status)) {
                    activeRow = row;
                }
            });

            if (!activeRow) {
                return;
            }

            const orderId = parseInt(activeRow.getAttribute("data-order-id") || "0", 10);
            if (!orderId) {
                return;
            }

            navigator.geolocation.getCurrentPosition(
                function (position) {
                    fetch("/api/rider/location", {
                        method: "POST",
                        credentials: "same-origin",
                        headers: {
                            "Content-Type": "application/json",
                            "X-Requested-With": "XMLHttpRequest",
                        },
                        body: JSON.stringify({
                            order_id: orderId,
                            lat: position.coords.latitude,
                            lng: position.coords.longitude,
                        }),
                    }).catch(function () {
                        // Ignore transient sync failures.
                    });
                },
                function () {
                    // Ignore denied location errors silently.
                },
                { enableHighAccuracy: true, maximumAge: 5000 }
            );
        }, 7000);
    }

    if (paymentMethod) {
        paymentMethod.addEventListener("change", togglePaymentMethodDetails);
        togglePaymentMethodDetails();
    }

    if (themeToggle) {
        themeToggle.addEventListener("click", toggleTheme);
    }

    initTheme();
    initScrollReveal();
    initWishlistButtons();
    bindCartActions();
    initQtySteppers();
    initMobileAuthForms();
    initEnhancedLoginForms();
    initRoutePrefetch();
    fetchCartState();
    initDashboardPolling();
    initTrackOrderPolling();
    initDeliveryLocationSync();
    updateCustomerCounters();
    updateDeliveryCounters();
});
