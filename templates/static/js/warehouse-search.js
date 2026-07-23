/**
 * Warehouse Search Page JavaScript
 * Handles die location search and filtering functionality
 */

// Load available alloys and racks on page load
document.addEventListener('DOMContentLoaded', function() {
    loadAvailableAlloys();
    loadAvailableRacks();

    // Auto-focus search input if no query present
    const searchInput = document.getElementById('search-q');
    if (!searchInput.value) {
        setTimeout(() => searchInput.focus(), 100);
    }
});

// Load available alloys for dropdown filter
function loadAvailableAlloys() {
    fetch('/warehouse/api/search/alloys')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const select = document.getElementById('search-alloy');
                // Only add options if not already populated from server-side rendering
                if (select.querySelectorAll('option').length <= 1) {
                    data.alloys.forEach(alloy => {
                        const option = document.createElement('option');
                        option.value = alloy;
                        option.textContent = alloy;
                        select.appendChild(option);
                    });

                    // Set current value if exists from URL
                    const urlParams = new URLSearchParams(window.location.search);
                    const currentAlloy = urlParams.get('alloy');
                    if (currentAlloy && data.alloys.includes(currentAlloy)) {
                        select.value = currentAlloy;
                    }
                }

                // Show filter by rack section if there are racks
                loadAvailableRacks();
            }
        })
        .catch(error => console.error('Error loading alloys:', error));
}

// Load available racks for dropdown filter
function loadAvailableRacks() {
    fetch('/warehouse/api/racks')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const select = document.getElementById('search-rack');
                // Only add options if not already populated from server-side rendering
                if (select.querySelectorAll('option').length <= 1) {
                    data.racks.forEach(rack => {
                        const option = document.createElement('option');
                        option.value = rack.id;
                        option.textContent = `${rack.rack_code} - ${rack.rack_name}`;
                        select.appendChild(option);
                    });

                    // Show filter by rack if there are racks
                    if (data.racks.length > 0) {
                        document.getElementById('filter-by-rack').style.display = 'block';

                        // Set current value if exists from URL
                        const urlParams = new URLSearchParams(window.location.search);
                        const currentRack = urlParams.get('rack');
                        if (currentRack && data.racks.some(r => r.id === currentRack)) {
                            select.value = currentRack;
                        }
                    } else {
                        document.getElementById('filter-by-rack').style.display = 'none';
                    }
                }
            }
        })
        .catch(error => console.error('Error loading racks:', error));
}

// Perform search with filters
function performSearch(event) {
    event.preventDefault();

    const baseUrl = '/warehouse/search?';
    const params = new URLSearchParams({
        q: document.getElementById('search-q').value.trim(),
        profile: document.getElementById('search-profile').value.trim(),
        alloy: document.getElementById('search-alloy').value,
        rack: document.getElementById('search-rack')?.value || ''
    });

    // Update current search term for form display (if in template)
    const qInput = event.target.querySelector('[name="q"]');
    if (qInput) {
        qInput.value = params.get('q');
    }

    window.location.href = baseUrl + params.toString();
}

// Handle quick die lookup from dashboard
function searchDie(event) {
    event.preventDefault();

    const dieCode = document.getElementById('quick-die-code').value.trim().toUpperCase();
    if (!dieCode) {
        showNotification('warning', 'Please enter a die code');
        return;
    }

    // Redirect to search page with parameter
    window.location.href = `/warehouse/search?q=${encodeURIComponent(dieCode)}`;
}

// Show notification message
function showNotification(type, message) {
    const alertClass = type === 'success' ? 'alert-success' : (type === 'warning' ? 'alert-warning' : 'alert-danger');

    const notification = document.createElement('div');
    notification.className = `fixed-top ${alertClass}`;
    notification.style.cssText = 'padding: 1rem; margin: 1rem; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `<i class="fas fa-${type === 'success' ? 'check-circle' : (type === 'warning' ? 'exclamation-triangle' : 'exclamation-circle')} me-2"></i>${message}`;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Handle barcode scanner auto-submit for search input
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && e.target.id === 'search-q') {
        e.preventDefault();
        document.getElementById('search-form').dispatchEvent(new Event('submit'));
    }
});

// Handle barcode scanner auto-submit for quick search input
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && e.target.id === 'quick-die-code') {
        e.preventDefault();
        document.getElementById('quick-search-form').dispatchEvent(new Event('submit'));
    }
});
