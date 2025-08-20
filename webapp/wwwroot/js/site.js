// site.js - JavaScript pour D&D GameMaster

// D&D GameMaster - Main JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    initBootstrapComponents();
    
    // Card animations
    initCardAnimations();
    
    // Form validations
    initFormValidations();
    
    // Page-specific initializations
    initPageSpecific();
    
    // Add fade-in class to main content for smooth page transitions
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.classList.add('fade-in');
    }
    
    // Navbar active state
    setActiveNavItem();
    
    // Log initialization
    console.log('D&D GameMaster JS initialized');
});

// Initialize Bootstrap components
function initBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.forEach(function(popoverTriggerEl) {
        new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Initialize dropdown components
    const dropdownElementList = [].slice.call(document.querySelectorAll('.dropdown-toggle'));
    dropdownElementList.forEach(function(dropdownToggleEl) {
        new bootstrap.Dropdown(dropdownToggleEl);
    });
}

// Card animations
function initCardAnimations() {
    const cards = document.querySelectorAll('.card:not(.no-animation)');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
            this.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.15)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.1)';
        });
    });
}

// Form validations
function initFormValidations() {
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // Confirmation for delete actions
    const deleteButtons = document.querySelectorAll('.delete-confirm');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
                e.preventDefault();
            }
        });
    });
}

// Set active nav item based on current URL
function setActiveNavItem() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        
        // Special case for home
        if (href === '/' && (currentPath === '/' || currentPath === '/Home' || currentPath === '/Home/Index')) {
            link.classList.add('active');
        }
        // Handle other nav items
        else if (href !== '/' && currentPath.startsWith(href)) {
            link.classList.add('active');
        }
    });
}

// Page-specific initializations
function initPageSpecific() {
    // Chat page: Auto-focus on message input and scroll to bottom
    const messageInput = document.getElementById('Message');
    if (messageInput) {
        messageInput.focus();
        
        const chatContainer = document.querySelector('.chat-container');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
            
            // Auto-scroll when new messages arrive
            const observer = new MutationObserver(() => {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            });
            
            observer.observe(chatContainer, { childList: true, subtree: true });
        }
    }
    
    // Character creation: Initialize stat allocation
    initStatAllocation();
    
    // Campaign creation: Initialize setting selection
    initSettingSelection();
}

// Character stat allocation
function initStatAllocation() {
    const statInputs = document.querySelectorAll('.stat-input');
    if (statInputs.length === 0) return;
    
    const pointsRemaining = document.getElementById('pointsRemaining');
    const totalPoints = 27; // Standard D&D 5e point buy
    
    statInputs.forEach(input => {
        input.addEventListener('change', calculateRemainingPoints);
    });
    
    function calculateRemainingPoints() {
        let used = 0;
        statInputs.forEach(input => {
            const value = parseInt(input.value) || 8;
            // D&D 5e point buy cost: 8 (0), 9 (1), 10 (2), 11 (3), 12 (4), 13 (5), 14 (7), 15 (9)
            const cost = value <= 13 
                ? value - 8 
                : value === 14 ? 7 : value === 15 ? 9 : 0;
            used += cost;
        });
        
        const remaining = totalPoints - used;
        if (pointsRemaining) {
            pointsRemaining.textContent = remaining;
            pointsRemaining.classList.toggle('text-danger', remaining < 0);
        }
    }
}

// Campaign setting selection
function initSettingSelection() {
    const settingSelect = document.getElementById('campaignSetting');
    const customSettingGroup = document.getElementById('customSettingGroup');
    
    if (settingSelect && customSettingGroup) {
        settingSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                customSettingGroup.classList.remove('d-none');
            } else {
                customSettingGroup.classList.add('d-none');
            }
        });
    }
} 