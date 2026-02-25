// FindMyNyumba Application JavaScript
// Global application state and shared functionality

// Application state
const AppState = {
    currentUser: null,
    currentView: 'landing',
    listings: [],
    savedListings: [],
    init() {
        this.loadSavedListings();
        this.setupEventListeners();
        this.updateUI();
    },
    loadSavedListings() {
        const saved = localStorage.getItem('savedListings');
        this.savedListings = saved ? JSON.parse(saved) : [];
    },
    saveListings() {
        localStorage.setItem('savedListings', JSON.stringify(this.savedListings));
    },
    toggleSavedListing(id) {
        const index = this.savedListings.indexOf(id.toString());
        if (index === -1) {
            this.savedListings.push(id.toString());
        } else {
            this.savedListings.splice(index, 1);
        }
        this.saveListings();
        this.updateSaveButtons();
        return this.savedListings.includes(id.toString());
    },
    isListingSaved(id) {
        return this.savedListings.includes(id.toString());
    },
    setupEventListeners() {
        // Mobile menu toggle
        const mobileMenuButton = document.getElementById('mobile-menu-button');
        if (mobileMenuButton) {
            mobileMenuButton.addEventListener('click', () => {
                const menu = document.getElementById('mobile-menu');
                if (menu) {
                    menu.classList.toggle('hidden');
                }
            });
        }

        // Close mobile menu when clicking outside
        document.addEventListener('click', (event) => {
            const mobileMenu = document.getElementById('mobile-menu');
            const menuButton = document.getElementById('mobile-menu-button');
            
            if (mobileMenu && !mobileMenu.classList.contains('hidden')) {
                if (!mobileMenu.contains(event.target) && !menuButton.contains(event.target)) {
                    mobileMenu.classList.add('hidden');
                }
            }
        });

        // Toggle switch functionality
        const toggleSwitches = document.querySelectorAll('.dot');
        toggleSwitches.forEach(switchEl => {
            const switchContainer = switchEl.parentElement;
            if (switchContainer && switchContainer.querySelector('input[type="checkbox"]')) {
                switchContainer.addEventListener('click', function() {
                    const checkbox = this.querySelector('input[type="checkbox"]');
                    checkbox.checked = !checkbox.checked;
                    
                    if (checkbox.checked) {
                        this.querySelector('.dot').style.transform = 'translateX(20px)';
                        this.style.backgroundColor = 'var(--orange)';
                    } else {
                        this.querySelector('.dot').style.transform = 'translateX(0)';
                        this.style.backgroundColor = 'var(--light-gray)';
                    }
                });
            }
        });

        // Initialize toggle switches
        this.initializeToggleSwitches();
    },
    initializeToggleSwitches() {
        const toggleSwitches = document.querySelectorAll('.dot');
        toggleSwitches.forEach(dot => {
            const switchContainer = dot.parentElement;
            if (switchContainer && dot.previousElementSibling && dot.previousElementSibling.type === 'checkbox') {
                const checkbox = dot.previousElementSibling;
                if (checkbox.checked) {
                    dot.style.transform = 'translateX(20px)';
                    switchContainer.style.backgroundColor = 'var(--orange)';
                } else {
                    dot.style.transform = 'translateX(0)';
                    switchContainer.style.backgroundColor = 'var(--light-gray)';
                }
            }
        });
    },
    updateSaveButtons() {
        // Update all save buttons on the page
        const saveButtons = document.querySelectorAll('#save-listing, #mobile-save-listing');
        saveButtons.forEach(button => {
            const listingId = this.getCurrentListingId();
            if (listingId) {
                this.updateSaveButtonState(button, this.isListingSaved(listingId));
            }
        });
    },
    getCurrentListingId() {
        // Extract listing ID from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('id') || '1'; // Default to '1' for demo
    },
    updateSaveButtonState(button, isSaved) {
        const icon = button.querySelector('i');
        if (isSaved) {
            icon.classList.remove('far');
            icon.classList.add('fas', 'text-orange-600');
            button.innerHTML = '<i class="fas fa-bookmark text-orange-600 mr-2"></i> Saved';
            button.classList.remove('bg-gray-200', 'hover:bg-gray-300', 'text-gray-800');
            button.classList.add('bg-orange-100', 'hover:bg-orange-200', 'text-orange-800');
        } else {
            icon.classList.remove('fas', 'text-orange-600');
            icon.classList.add('far');
            button.innerHTML = '<i class="far fa-bookmark mr-2"></i> Save Listing';
            button.classList.remove('bg-orange-100', 'hover:bg-orange-200', 'text-orange-800');
            button.classList.add('bg-gray-200', 'hover:bg-gray-300', 'text-gray-800');
        }
    },
    updateUI() {
        // Update UI elements based on application state
        this.updateSaveButtons();
    }
};

// Utility functions
const Utils = {
    formatCurrency(amount) {
        return `ZMW ${amount.toLocaleString()}`;
    },
    formatDate(dateString) {
        const options = { year: 'numeric', month: 'short', day: 'numeric' };
        return new Date(dateString).toLocaleDateString(undefined, options);
    },
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Gallery functionality
const Gallery = {
    currentIndex: 0,
    init() {
        this.setupEventListeners();
    },
    setupEventListeners() {
        const thumbnails = document.querySelectorAll('.gallery-thumbnail');
        thumbnails.forEach((thumb, index) => {
            thumb.addEventListener('click', () => {
                this.showImage(index);
            });
        });
    },
    showImage(index) {
        const thumbnails = document.querySelectorAll('.gallery-thumbnail');
        const mainImage = document.getElementById('main-image');
        
        // Remove active class from all thumbnails
        thumbnails.forEach(t => t.classList.remove('active'));
        
        // Add active class to selected thumbnail
        thumbnails[index].classList.add('active');
        
        // In a real implementation, this would change the main image
        // For now, we'll just log the action
        console.log(`Showing image ${index}`);
        
        this.currentIndex = index;
    }
};

// Form validation utilities
const FormValidator = {
    validateRequired(element) {
        const value = element.value.trim();
        if (!value) {
            this.setInvalid(element);
            return false;
        }
        this.setValid(element);
        return true;
    },
    validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },
    validatePhone(phone) {
        const re = /^\+?[\d\s\-\(\)]{10,}$/;
        return re.test(phone);
    },
    setInvalid(element) {
        element.classList.add('border-red-500');
        element.classList.remove('border-gray-300');
    },
    setValid(element) {
        element.classList.remove('border-red-500');
        element.classList.add('border-gray-300');
    },
    clearValidation(element) {
        element.classList.remove('border-red-500');
        element.classList.remove('border-green-500');
        element.classList.add('border-gray-300');
    }
};

// Search functionality
const Search = {
    init() {
        const searchForm = document.getElementById('search-form');
        if (searchForm) {
            searchForm.addEventListener('submit', this.handleSearch.bind(this));
        }
    },
    handleSearch(e) {
        e.preventDefault();
        
        // Get search values
        const university = document.querySelector('#search-form select')?.value;
        const location = document.querySelector('#search-form input[placeholder="Location"]')?.value;
        const priceRange = document.querySelector('#search-form input[placeholder="Price Range"]')?.value;
        const verifiedOnly = document.querySelector('#search-form input[type="checkbox"]')?.checked;
        
        // In a real app, this would filter listings
        console.log('Search submitted:', { university, location, priceRange, verifiedOnly });
        
        // Redirect to browse page with filters
        window.location.href = 'browse.html';
    }
};

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    AppState.init();
    Search.init();
    
    // Initialize gallery if on listing page
    if (document.getElementById('main-image')) {
        Gallery.init();
    }
    
    // Set up save listing functionality
    const saveButtons = document.querySelectorAll('#save-listing, #mobile-save-listing');
    saveButtons.forEach(button => {
        button.addEventListener('click', function() {
            const listingId = AppState.getCurrentListingId();
            const isSaved = AppState.toggleSavedListing(listingId);
            
            // Update all save buttons
            const allSaveButtons = document.querySelectorAll('#save-listing, #mobile-save-listing');
            allSaveButtons.forEach(btn => {
                AppState.updateSaveButtonState(btn, isSaved);
            });
        });
    });
    
    // Initialize saved state on page load
    window.addEventListener('load', function() {
        const listingId = AppState.getCurrentListingId();
        if (listingId) {
            const saveButtons = document.querySelectorAll('#save-listing, #mobile-save-listing');
            saveButtons.forEach(button => {
                AppState.updateSaveButtonState(button, AppState.isListingSaved(listingId));
            });
        }
    });
});

// Export for potential module usage (if supported)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AppState, Utils, Gallery, FormValidator, Search };
}