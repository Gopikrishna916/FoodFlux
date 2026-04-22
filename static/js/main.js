document.addEventListener('DOMContentLoaded', function () {
    const paymentMethod = document.getElementById('paymentMethod');
    const upiQRSection = document.getElementById('upiQRSection');
    const upiApps = document.getElementById('upiApps');

    function toggleUpiPaymentDetails() {
        if (!paymentMethod || !upiQRSection || !upiApps) {
            return;
        }

        const showUpi = paymentMethod.value === 'UPI';
        upiQRSection.classList.toggle('d-none', !showUpi);
        upiApps.classList.toggle('d-none', !showUpi);
    }

    if (paymentMethod) {
        paymentMethod.addEventListener('change', toggleUpiPaymentDetails);
        toggleUpiPaymentDetails();
    }

    // Confirmation dialogs for delete actions
    const confirms = document.querySelectorAll('a[onclick]');
    confirms.forEach((link) => {
        if (link.getAttribute('onclick')?.includes('confirm')) {
            link.addEventListener('click', function (event) {
                const ok = confirm('Are you sure you want to continue?');
                if (!ok) event.preventDefault();
            });
        }
    });
    
    // Add animations to elements as they come into view
    const animateOnScroll = document.querySelectorAll('.fade-in, .slide-in, .slide-up');
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        
        animateOnScroll.forEach(el => observer.observe(el));
    }
    
    // Smooth scroll behavior for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            }
        });
    });
    
    // Add hover effects to buttons
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // Add cart animation when item is added
    const addToCartButtons = document.querySelectorAll('a[href*="add_to_cart"]');
    addToCartButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const cartBadge = document.querySelector('.badge-primary');
            if (cartBadge) {
                cartBadge.classList.add('bounce');
                setTimeout(() => cartBadge.classList.remove('bounce'), 600);
            }
        });
    });
    
    // Delivery notification popup for delivered orders
    function checkDeliveryStatus() {
        const orderIdMatch = window.location.pathname.match(/\/track_order\/(\d+)/);
        if (orderIdMatch) {
            const orderId = orderIdMatch[1];
            fetch(`/api/order/check/${orderId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'Delivered') {
                        showDeliveryNotification(orderId);
                    }
                })
                .catch(err => console.log('Error checking delivery status:', err));
        }
    }
    
    // Show delivery notification popup
    function showDeliveryNotification(orderId) {
        const notification = document.createElement('div');
        notification.className = 'alert alert-success alert-dismissible fade show bounce-in';
        notification.setAttribute('role', 'alert');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            width: 400px;
            z-index: 10000;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            max-width: calc(100% - 40px);
        `;
        
        notification.innerHTML = `
            <div style="animation: slideInRight 0.5s ease;">
                <h4 class="alert-heading">🎉 Order Delivered!</h4>
                <p>Your order #${orderId} has been delivered successfully!</p>
                <hr>
                <p class="mb-0">Enjoy your delicious food! 😋</p>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 8 seconds
        setTimeout(() => {
            notification.remove();
        }, 8000);
    }
    
    // Check delivery status on track order page
    if (window.location.pathname.includes('/track_order/')) {
        checkDeliveryStatus();
    }
    
    // Format currency input
    const priceInputs = document.querySelectorAll('input[type="number"][step="0.01"]');
    priceInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const value = parseFloat(this.value);
            if (!isNaN(value)) {
                this.value = value.toFixed(2);
            }
        });
    });
    
    // Add loading animation to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
            }
        });
    });
    
    // Quantity input validation
    const qtyInputs = document.querySelectorAll('input[name^="qty_"]');
    qtyInputs.forEach(input => {
        input.addEventListener('change', function() {
            const value = parseInt(this.value);
            if (value < 1) {
                this.value = 1;
            } else if (value > 99) {
                this.value = 99;
            }
        });
    });
    
    // Add keyboard shortcut for search
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === '/') {
            event.preventDefault();
            const searchInput = document.querySelector('input[name="q"]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
    });
    
    // Add CSS for slideInRight animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
    `;
    document.head.appendChild(style);
});
