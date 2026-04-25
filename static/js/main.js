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

    function initOrderDeliveryNotifier() {
        const match = window.location.pathname.match(/\/track_order\/(\d+)/);
        if (!match) {
            return;
        }

        const orderId = match[1];
        fetch(`/api/order/check/${orderId}`)
            .then((response) => response.json())
            .then((data) => {
                if (data.status === "Delivered") {
                    showDeliveredToast(orderId);
                }
            })
            .catch(() => {
                // Do not surface noisy errors for status polling.
            });
    }

    function showDeliveredToast(orderId) {
        const toast = document.createElement("div");
        toast.className = "alert alert-success";
        toast.style.position = "fixed";
        toast.style.top = "16px";
        toast.style.right = "16px";
        toast.style.width = "min(420px, calc(100% - 32px))";
        toast.style.zIndex = "10000";
        toast.style.boxShadow = "0 16px 30px rgba(15, 23, 42, 0.18)";
        toast.innerHTML = `<strong>Order Delivered</strong><div>Your order #${orderId} has arrived. Enjoy your meal.</div>`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 7000);
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
    initOrderDeliveryNotifier();
});
