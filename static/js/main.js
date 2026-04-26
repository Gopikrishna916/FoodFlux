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

    function statusBadgeClass(status) {
        if (status === "Delivered") {
            return "badge bg-success order-status-badge";
        }
        if (status === "On the Way" || status === "Picked Up") {
            return "badge bg-primary order-status-badge";
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

    function initRealtime() {
        if (typeof io === "undefined") {
            return;
        }

        const socket = io({ transports: ["websocket", "polling"] });

        socket.on("connect", function () {
            // Connected; rooms are assigned server-side using session.
        });

        socket.on("order_event", function (payload) {
            if (!payload || !payload.id) {
                return;
            }

            updateRowByOrderId("customerOrdersTable", payload);
            updateRowByOrderId("deliveryOrdersTable", payload);
            updateRowByOrderId("managerOrdersTable", payload, { removeOnDelivered: true });
            updateCustomerCounters();
            updateDeliveryCounters();
            handleTrackOrderRealtime(payload);

            const eventMessage = {
                order_created: `Order #${payload.id} placed successfully.`,
                rider_assigned: `Delivery partner ${payload.delivery_person || "assigned"} for order #${payload.id}.`,
                order_accepted: `Order #${payload.id} accepted by restaurant.`,
                restaurant_ready: `Order #${payload.id} is ready for pickup.`,
                preparing: `Order #${payload.id} is being prepared.`,
                rider_accepted: `Rider accepted order #${payload.id}.`,
                picked_up: `Order #${payload.id} is out for delivery.`,
                on_the_way: `Order #${payload.id} is on the way.`,
                near_customer: `Rider is near your location for order #${payload.id}.`,
                delivered: `Order #${payload.id} delivered.`,
                cancelled: `Order #${payload.id} was cancelled.`,
            };

            const text = eventMessage[payload.event];
            if (text) {
                const css = payload.event === "delivered" ? "alert-success" : "alert-info";
                showLiveToast("Live Update", text, css);
            }
        });

        socket.on("rider_location", function (payload) {
            if (!payload || !payload.order_id) {
                return;
            }
            window.latestRiderLocation = payload;

            const mapStatus = document.getElementById("riderLiveLocationText");
            if (mapStatus) {
                mapStatus.textContent = `Rider location updated: ${payload.lat.toFixed(5)}, ${payload.lng.toFixed(5)}`;
            }

            if (window.updateRiderMapMarker) {
                window.updateRiderMapMarker(payload.lat, payload.lng);
            }
        });

        const role = document.body.getAttribute("data-role");
        if (role === "delivery_partner" && navigator.geolocation) {
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
                        socket.emit("rider_location_update", {
                            order_id: orderId,
                            lat: position.coords.latitude,
                            lng: position.coords.longitude,
                        });
                    },
                    function () {
                        // Ignore denied location errors silently.
                    },
                    { enableHighAccuracy: true, maximumAge: 5000 }
                );
            }, 5000);
        }
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
    initQtySteppers();
    initRealtime();
    updateCustomerCounters();
    updateDeliveryCounters();
});
