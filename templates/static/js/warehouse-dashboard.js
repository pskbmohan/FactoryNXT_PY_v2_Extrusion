/**
 * Warehouse Dashboard JavaScript
 * Handles real-time rack visualization and statistics updates
 */

// Load warehouse overview statistics
function loadWarehouseStats() {
    fetch('/warehouse/api/stats/overview')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const stats = data.statistics;

                // Update stat cards
                document.getElementById('stat-total-racks').textContent = stats.total_racks || 0;
                document.getElementById('stat-total-dies').textContent = stats.total_dies_stored || 0;
                document.getElementById('stat-available-slots').textContent = calculateAvailableSlots(stats);
                document.getElementById('stat-recent-tx').textContent = stats.recent_transactions_24h || 0;

                // Update rack status breakdown
                updateRackStatusCards(stats.racks_by_status);
            }
        })
        .catch(error => {
            console.error('Error loading warehouse stats:', error);
            showNotification('danger', 'Failed to load statistics');
        });
}

// Calculate available slots from rack data
function calculateAvailableSlots(stats) {
    let total = 0;
    if (stats.racks_by_status && Array.isArray(stats.racks_by_status)) {
        stats.racks_by_status.forEach(status => {
            // This would need actual available slot calculation per rack type
            total += status.count * 15; // Rough estimate for demo
        });
    }
    return total > 0 ? total : '-';
}

// Update rack status cards based on filter selection
document.getElementById('filter-rack-type').addEventListener('change', function() {
    loadRacks();
});

// Load racks visualization
function loadRacks() {
    const typeFilter = document.getElementById('filter-rack-type')?.value || '';

    fetch(`/warehouse/api/racks${typeFilter ? `?status=${typeFilter}` : ''}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.racks.length > 0) {
                renderRackGrid(data.racks);
            } else {
                document.getElementById('racks-container').innerHTML = `
                    <div class="text-center py-4 text-muted">
                        <i class="fas fa-boxes-open fa-3x mb-2"></i><br>
                        No racks found matching the current filter.
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading racks:', error);
            document.getElementById('racks-container').innerHTML = `
                <div class="alert alert-danger">Failed to load rack data.</div>
            `;
        });
}

// Render rack grid visualization
function renderRackGrid(racks) {
    const container = document.getElementById('racks-container');
    let html = '<div class="row g-3">';

    racks.forEach(rack => {
        const fillPct = ((rack.available_slots / rack.total_slots) * 100).toFixed(0);
        const isFull = fillPct === '0' || (rack.filled_slots && rack.filled_slots >= rack.total_slots);

        html += `
            <div class="col-md-4 col-lg-3">
                <a href="/warehouse/rack/${rack.id}" class="text-decoration-none text-dark">
                    <div class="card h-100 ${isFull ? 'border-danger' : ''} rack-item" data-rack-id="${rack.id}">
                        <div class="card-header d-flex justify-content-between align-items-center
                                    ${getRackStatusColor(rack.status)} text-white">
                            <h6 class="mb-0"><i class="fas fa-box me-1"></i>${escapeHtml(rack.rack_name)}</h6>
                        </div>
                        <div class="card-body p-3">
                            <small class="text-muted d-block mb-1">${rack.rack_code}</small>
                            ${rack.location_zone ? `<span class="badge bg-info me-1">${escapeHtml(rack.location_zone)}</span>` : ''}
                            ${getRackTypeBadge(rack.rack_type)}

                            <div class="mt-3">
                                <div class="d-flex justify-content-between mb-1">
                                    <small>Available</small>
                                    <strong>${rack.available_slots}/${rack.total_slots}</strong>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-success progress-bar-striped progress-bar-animated"
                                         role="progressbar" style="width: ${fillPct}%">
                                        ${Math.round(fillPct)}%
                                    </div>
                                </div>
                            </div>

                            <div class="mt-3 text-center">
                                <button class="btn btn-sm btn-outline-primary">View Slots</button>
                            </div>
                        </div>
                    </div>
                </a>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

// Get rack status color class
function getRackStatusColor(status) {
    const colors = {
        'AVAILABLE': 'bg-success',
        'IN_USE': 'bg-primary',
        'MAINTENANCE': 'bg-secondary'
    };
    return colors[status] || 'bg-dark';
}

// Get rack type badge HTML
function getRackTypeBadge(rackType) {
    const badges = {
        'STORAGE_RACK': '<span class="badge bg-info">Storage</span>',
        'QUICK_CHANGE_RACK': '<span class="badge bg-warning text-dark">Quick Change</span>',
        'INPRESS_RACK': '<span class="badge bg-secondary">In-Press</span>'
    };
    return badges[rackType] || '';
}

// Load recent activity (transactions)
function loadRecentActivity() {
    fetch('/warehouse/api/transactions?limit=10')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.transactions.length > 0) {
                renderRecentTransactions(data.transactions);
            } else {
                document.getElementById('recent-activity-table').innerHTML = `
                    <tr><td colspan="4" class="text-center py-3 text-muted">No recent activity</td></tr>
                `;
            }
        })
        .catch(error => console.error('Error loading recent activity:', error));
}

// Render recent transactions table
function renderRecentTransactions(transactions) {
    const tbody = document.getElementById('recent-activity-table');
    let html = '';

    transactions.forEach(tx => {
        const typeBadge = getTypeBadge(tx.transaction_type);
        const timeAgo = getTimeAgo(tx.transaction_time);

        html += `
            <tr>
                <td>${typeBadge}</td>
                <td><strong>${escapeHtml(tx.die_code || '-')}</strong></td>
                <td>
                    ${tx.rack_id ? `<span class="badge bg-info">${escapeHtml(tx.rack_id.substring(0, 8))}</span>` : '-'}
                    ${tx.slot_number ? ` Slot ${tx.slot_number}` : ''}
                </td>
                <td><small class="text-muted">${timeAgo}</small></td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// Get type badge HTML
function getTypeBadge(type) {
    const badges = {
        'IN': '<span class="badge bg-success">IN</span>',
        'OUT': '<span class="badge bg-danger">OUT</span>',
        'TRANSFER': '<span class="badge bg-warning text-dark">Transfer</span>'
    };
    return badges[type] || `<span class="badge bg-secondary">${type}</span>`;
}

// Format time ago display
function getTimeAgo(timestamp) {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
}

// Search die by code or barcode
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

// Handle barcode scanner auto-submit for quick search
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && e.target.id === 'quick-die-code') {
        document.getElementById('quick-search-form').dispatchEvent(new Event('submit'));
    }
});

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
