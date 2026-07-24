/**
 * Warehouse Search - Modern JavaScript Module
 *
 * Features:
 * - Debounced search for better performance
 * - Keyboard shortcuts (Ctrl+F focus, Escape clear, Enter submit)
 * - Real-time filtering with visual feedback
 * - Pagination controls
 * - Autocomplete suggestions
 * - Barcode scanner support
 * - Search statistics display
 */

(function() {
    'use strict';

    // Configuration constants
    const CONFIG = {
        DEBOUNCE_DELAY: 300,          // Delay for debounced search (ms)
        AUTOFOCUS_TIMEOUT: 150,       // Timeout before auto-focusing input
        MIN_SEARCH_LENGTH: 2,         // Minimum characters for autocomplete
        MAX_AUTOCOMPLETE_RESULTS: 10, // Max suggestions shown
        BARCODE_SCANNER_DELAY: 100    // Delay after barcode scan (ms)
    };

    // State management
    const state = {
        currentSearch: null,
        debounceTimer: null,
        isSearching: false,
        pagination: { page: 1, perPage: 50, totalPages: 1 }
    };

    /**
     * Initialize search module on DOM ready
     */
    document.addEventListener('DOMContentLoaded', function() {
        initSearchUI();
        loadFacets();
        setupKeyboardShortcuts();

        // Check for URL parameters to auto-populate and search
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('q')) {
            document.getElementById('search-q').value = urlParams.get('q');
            performSearch({ preventDefault: () => {} });
        } else {
            // Auto-focus for barcode scanner usage
            setTimeout(() => focusSearchInput(), CONFIG.AUTOFOCUS_TIMEOUT);
        }
    });

    /**
     * Initialize all search UI components and event listeners
     */
    function initSearchUI() {
        const form = document.getElementById('search-form');
        if (form) {
            form.addEventListener('submit', handleSearchSubmit);
        }

        setupSearchInput();
        updateFilterVisibility();
        showLoadingIndicator(false);
    }

    /**
     * Set up search input with debouncing and autocomplete
     */
    function setupSearchInput() {
        const searchInput = document.getElementById('search-q');
        if (!searchInput) return;

        // Debounced search on typing (for real-time suggestions)
        searchInput.addEventListener('input', debounce(function(e) {
            handleSearchInput(e);
        }, CONFIG.DEBOUNCE_DELAY));

        // Handle autocomplete selection
        const autocompleteList = document.getElementById('autocomplete-list');
        if (autocompleteList) {
            autocompleteList.addEventListener('click', handleAutocompleteClick);
        }
    }

    /**
     * Load searchable facets for filter dropdowns
     */
    function loadFacets() {
        fetch('/warehouse/api/search/facets')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    populateAlloyDropdown(data.alloys);
                    populateProfileDropdown(data.profiles);
                    updateRackFilterVisibility();
                } else {
                    console.error('Failed to load search facets:', data.error);
                }
            })
            .catch(error => {
                console.error('Error loading facets:', error);
            });
    }

    /**
     * Populate alloy dropdown with available options
     */
    function populateAlloyDropdown(alloys) {
        const select = document.getElementById('search-alloy');
        if (!select || !alloys) return;

        // Only add options if not already populated from server-side rendering
        if (select.querySelectorAll('option').length <= 1) {
            alloys.forEach(item => {
                const option = document.createElement('option');
                option.value = item.name;
                option.textContent = `${item.name} (${item.count})`;
                select.appendChild(option);
            });

            // Set current value from URL if exists
            const urlParams = new URLSearchParams(window.location.search);
            const currentAlloy = urlParams.get('alloy');
            if (currentAlloy && alloys.some(a => a.name === currentAlloy)) {
                select.value = currentAlloy;
            }
        }

        // Show/hide alloy filter based on availability
        document.getElementById('filter-by-alloy')?.classList.toggle('d-none', !alloys.length);
    }

    /**
     * Populate profile dropdown with available options
     */
    function populateProfileDropdown(profiles) {
        const select = document.getElementById('search-profile');
        if (!select || !profiles) return;

        // Only add options if not already populated from server-side rendering
        if (select.querySelectorAll('option').length <= 1) {
            profiles.forEach(item => {
                const option = document.createElement('option');
                option.value = item.code;
                option.textContent = `${item.code} (${item.count})`;
                select.appendChild(option);
            });

            // Set current value from URL if exists
            const urlParams = new URLSearchParams(window.location.search);
            const currentProfile = urlParams.get('profile');
            if (currentProfile && profiles.some(p => p.code === currentProfile)) {
                select.value = currentProfile;
            }
        }

        // Show/hide profile filter based on availability
        document.getElementById('filter-by-profile')?.classList.toggle('d-none', !profiles.length);
    }

    /**
     * Update visibility of rack filter section
     */
    function updateRackFilterVisibility() {
        const filterSection = document.getElementById('filter-by-rack');
        if (!filterSection) return;

        // Check if there are any racks with items
        fetch('/warehouse/api/racks')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.racks.length > 0) {
                    populateRackDropdown(data.racks);
                    filterSection.classList.remove('d-none');

                    // Set current rack from URL if exists
                    const urlParams = new URLSearchParams(window.location.search);
                    const currentRack = urlParams.get('rack');
                    if (currentRack && data.racks.some(r => r.id === currentRack)) {
                        filterSection.querySelector('select').value = currentRack;
                    }
                } else {
                    filterSection.classList.add('d-none');
                }
            })
            .catch(error => {
                console.error('Error loading racks:', error);
                filterSection.classList.add('d-none');
            });
    }

    /**
     * Populate rack dropdown with available options
     */
    function populateRackDropdown(racks) {
        const select = document.getElementById('search-rack');
        if (!select || !racks) return;

        // Only add options if not already populated from server-side rendering
        if (select.querySelectorAll('option').length <= 1) {
            racks.forEach(rack => {
                const option = document.createElement('option');
                option.value = rack.id;
                option.textContent = `${rack.rack_code} - ${rack.rack_name}`;
                select.appendChild(option);
            });

            // Set current value from URL if exists
            const urlParams = new URLSearchParams(window.location.search);
            const currentRack = urlParams.get('rack');
            if (currentRack && racks.some(r => r.id === currentRack)) {
                select.value = currentRack;
            }
        }
    }

    /**
     * Handle search input changes with debouncing
     */
    function handleSearchInput(event) {
        const searchTerm = event.target.value.trim();

        // Show/hide autocomplete based on input length
        showAutocomplete(searchTerm);

        // Update current search state for pagination display
        if (searchTerm.length >= CONFIG.MIN_SEARCH_LENGTH) {
            document.getElementById('current-search-term')?.textContent ||
                createSearchStatsDisplay(searchTerm);
        }
    }

    /**
     * Show autocomplete suggestions based on search term
     */
    function showAutocomplete(searchTerm) {
        const list = document.getElementById('autocomplete-list');
        if (!list) return;

        // Clear previous results and hide if too short
        if (searchTerm.length < CONFIG.MIN_SEARCH_LENGTH) {
            list.innerHTML = '';
            list.classList.add('d-none');
            return;
        }

        fetch(`/warehouse/api/search/dies/autocomplete?q=${encodeURIComponent(searchTerm)}&limit=${CONFIG.MAX_AUTOCOMPLETE_RESULTS}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.suggestions.length > 0) {
                    displayAutocompleteSuggestions(data.suggestions, list);
                } else {
                    list.innerHTML = '<li class="list-group-item text-muted">No suggestions found</li>';
                    list.classList.remove('d-none');
                }
            })
            .catch(error => {
                console.error('Error loading autocomplete:', error);
                list.classList.add('d-none');
            });
    }

    /**
     * Display autocomplete suggestions in dropdown
     */
    function displayAutocompleteSuggestions(suggestions, container) {
        if (suggestions.length === 0) return;

        container.innerHTML = '';

        suggestions.forEach(item => {
            const li = document.createElement('li');
            li.className = 'list-group-item list-group-item-action';
            li.dataset.value = item.value;
            li.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span><strong>${item.display || item.value}</strong></span>
                    ${item.type === 'profile' ? '<span class="badge bg-info">Profile</span>' : ''}
                </div>
            `;
            container.appendChild(li);
        });

        container.classList.remove('d-none');
    }

    /**
     * Handle autocomplete item selection
     */
    function handleAutocompleteClick(event) {
        const listItem = event.target.closest('[data-value]');
        if (!listItem) return;

        const value = listItem.dataset.value;
        document.getElementById('search-q').value = value;
        document.getElementById('autocomplete-list').classList.add('d-none');

        // Trigger search after selection with slight delay for visual feedback
        setTimeout(() => {
            handleSearchSubmit({ preventDefault: () => {} });
        }, 150);
    }

    /**
     * Handle form submission (search button or Enter key)
     */
    function handleSearchSubmit(event) {
        event.preventDefault();

        const searchTerm = document.getElementById('search-q').value.trim();
        if (!searchTerm && !hasActiveFilters()) {
            showNotification('warning', 'Please enter a search term or select filters');
            focusSearchInput();
            return;
        }

        performSearch(searchTerm);
    }

    /**
     * Perform the actual search with current form values
     */
    function performSearch(searchTerm) {
        const params = buildSearchParams(searchTerm);

        showLoadingIndicator(true, 'Searching...');
        state.currentSearch = searchTerm;

        fetch(`/warehouse/search?${new URLSearchParams(params).toString()}`)
            .then(response => response.text())
            .then(html => {
                // Parse and replace content (simulating navigation without full reload)
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                document.getElementById('search-results-container')?.replaceWith(
                    doc.getElementById('search-results-container').cloneNode(true)
                );

                // Re-initialize event listeners for new elements
                reattachEventListeners();

                showLoadingIndicator(false);
            })
            .catch(error => {
                console.error('Search error:', error);
                showNotification('danger', 'Search failed. Please try again.');
                showLoadingIndicator(false);
            });
    }

    /**
     * Build search parameters object from form values
     */
    function buildSearchParams(searchTerm) {
        return {
            q: searchTerm,
            profile: document.getElementById('search-profile')?.value.trim() || '',
            alloy: document.getElementById('search-alloy')?.value || '',
            rack: document.getElementById('search-rack')?.value || ''
        };
    }

    /**
     * Check if any filters are currently active
     */
    function hasActiveFilters() {
        const profile = document.getElementById('search-profile');
        const alloy = document.getElementById('search-alloy');
        const rack = document.getElementById('search-rack');

        return (profile && profile.value) ||
               (alloy && alloy.value) ||
               (rack && rack.value);
    }

    /**
     * Set up keyboard shortcuts for search interface
     */
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Ctrl+F or Cmd+F to focus search input
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                focusSearchInput();
                return;
            }

            // Escape key clears search and closes autocomplete
            if (e.key === 'Escape') {
                const autocomplete = document.getElementById('autocomplete-list');
                if (!autocomplete.classList.contains('d-none')) {
                    e.preventDefault();
                    autocomplete.classList.add('d-none');
                    return;
                }

                // Clear current search
                if (state.currentSearch) {
                    document.getElementById('search-q').value = '';
                    state.currentSearch = null;
                    handleSearchSubmit({ preventDefault: () => {} });
                }
                return;
            }

            // Enter key submits form when not in autocomplete list
            if (e.key === 'Enter' && e.target.id === 'search-q') {
                const autocomplete = document.getElementById('autocomplete-list');
                if (!autocomplete.classList.contains('d-none')) {
                    // If on an item, select it
                    const selected = autocomplete.querySelector('.active');
                    if (selected) {
                        handleAutocompleteClick({ target: selected });
                        e.preventDefault();
                        return;
                    }
                }
                submitFormOnEnter(e);
            }

            // Arrow keys navigate autocomplete list
            if (e.key.startsWith('Arrow') && !document.getElementById('autocomplete-list').classList.contains('d-none')) {
                navigateAutocompleteList(e);
            }
        });

        // Handle barcode scanner input pattern (enters followed by Enter)
        document.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && e.target.id === 'search-q') {
                submitFormOnEnter(e);
            }
        });
    }

    /**
     * Submit form when Enter is pressed on search input
     */
    function submitFormOnEnter(event) {
        // Small delay to allow autocomplete selection first
        setTimeout(() => {
            const autocomplete = document.getElementById('autocomplete-list');
            if (autocomplete.classList.contains('d-none')) {
                event.preventDefault();
                document.getElementById('search-form').dispatchEvent(new Event('submit'));
            }
        }, 10);
    }

    /**
     * Navigate through autocomplete list with arrow keys
     */
    function navigateAutocompleteList(event) {
        const items = Array.from(document.querySelectorAll('#autocomplete-list .list-group-item'));
        if (!items.length) return;

        const activeItem = document.querySelector('#autocomplete-list .active');
        let currentIndex = activeItem ? items.indexOf(activeItem) : -1;

        switch (event.key) {
            case 'ArrowDown':
                event.preventDefault();
                currentIndex = Math.min(currentIndex + 1, items.length - 1);
                break;
            case 'ArrowUp':
                event.preventDefault();
                currentIndex = Math.max(currentIndex - 1, 0);
                break;
            default:
                return;
        }

        // Update active item styling
        if (activeItem) {
            activeItem.classList.remove('active', 'bg-light');
        }
        items[currentIndex].classList.add('active', 'bg-light');
    }

    /**
     * Focus the search input field
     */
    function focusSearchInput() {
        const input = document.getElementById('search-q');
        if (input) {
            input.focus();
            // Select all text for easy replacement (barcode scanner friendly)
            input.select();
        }
    }

    /**
     * Create search statistics display element
     */
    function createSearchStatsDisplay(searchTerm) {
        const container = document.getElementById('search-results-container');
        if (!container || !document.querySelector('#current-search-stats')) return;

        let statsHtml = `
            <div class="mb-3">
                <span id="current-search-term" class="badge bg-primary me-2">${escapeHtml(searchTerm)}</span>
                ${hasActiveFilters() ? '<span class="badge bg-secondary">Filters Active</span>' : ''}
            </div>
        `;

        const statsElement = document.createElement('div');
        statsElement.id = 'current-search-stats';
        statsElement.innerHTML = statsHtml;

        container.querySelector('.text-center')?.parentNode.insertBefore(statsElement,
            container.querySelector('.text-center')?.parentNode.firstChild);
    }

    /**
     * Show/hide loading indicator during search operations
     */
    function showLoadingIndicator(showing, message = 'Searching...') {
        const resultsContainer = document.getElementById('search-results-container');
        if (!resultsContainer) return;

        if (showing) {
            state.isSearching = true;
            resultsContainer.innerHTML = `
                <div class="text-center py-5">
                    <i class="fas fa-spinner fa-spin fa-3x mb-3 text-primary"></i>
                    <h5>${message}</h5>
                    <p class="text-muted">Please wait while we search the warehouse database...</p>
                </div>
            `;
        } else {
            state.isSearching = false;
        }
    }

    /**
     * Show notification message to user
     */
    function showNotification(type, message) {
        const alertClass = type === 'success' ? 'alert-success' :
                          (type === 'warning' ? 'alert-warning' : 'alert-danger');

        const notification = document.createElement('div');
        notification.className = `fixed-top ${alertClass} shadow`;
        notification.style.cssText = 'padding: 1rem; margin: 1rem; z-index: 9999; min-width: 300px;';

        const icons = {
            success: 'check-circle',
            warning: 'exclamation-triangle',
            danger: 'exclamation-circle'
        };

        notification.innerHTML = `
            <i class="fas fa-${icons[type]} me-2"></i>${message}
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    /**
     * Reattach event listeners after DOM updates from AJAX responses
     */
    function reattachEventListeners() {
        // Recreate autocomplete listener if list exists in new content
        const newAutocomplete = document.getElementById('autocomplete-list');
        if (newAutocomplete) {
            newAutocomplete.addEventListener('click', handleAutocompleteClick);
        }

        // Rebind keyboard shortcuts for search input
        const newSearchInput = document.getElementById('search-q');
        if (newSearchInput && !newSearchInput.hasAttribute('data-listeners-bound')) {
            setupSearchInput();
            newSearchInput.setAttribute('data-listeners-bound', 'true');
        }
    }

    /**
     * Escape HTML to prevent XSS attacks
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Debounce function for performance optimization
     */
    function debounce(func, wait) {
        clearTimeout(state.debounceTimer);
        state.debounceTimer = setTimeout(() => func.apply(this, arguments), wait);
    }

    // Expose public API for external use if needed
    window.WarehouseSearch = {
        focus: focusSearchInput,
        performSearch: performSearch,
        clearSearch: function() {
            document.getElementById('search-q').value = '';
            state.currentSearch = null;
            handleSearchSubmit({ preventDefault: () => {} });
        }
    };

})();
