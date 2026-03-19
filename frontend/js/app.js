document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Navbar Toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    
    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
        });
    }

    // 2. Mobile Filters Toggle (Browse Page)
    const toggleFiltersBtn = document.getElementById('toggle-filters');
    const closeFiltersBtn = document.getElementById('close-filters');
    const filtersSidebar = document.getElementById('filters-sidebar');

    if (toggleFiltersBtn && filtersSidebar) {
        toggleFiltersBtn.addEventListener('click', () => {
            filtersSidebar.classList.remove('filters-closed');
            filtersSidebar.classList.add('filters-open');
        });
    }

    if (closeFiltersBtn && filtersSidebar) {
        closeFiltersBtn.addEventListener('click', () => {
            filtersSidebar.classList.remove('filters-open');
            filtersSidebar.classList.add('filters-closed');
        });
    }
});
