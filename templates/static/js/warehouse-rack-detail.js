/**
 * Warehouse Rack Detail Page JavaScript
 * Handles slot visualization and die assignment operations
 */

// Load rack information on page load
function loadRackInfo(rackId) {
    fetch(`/warehouse/api/racks/${rackId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.rack) {
                renderRackInfo(data.rack);
                setTimeout(() => loadRackSlots(rackId), 500); // Load slots after info renders
            } else {
                showError('Rack not found or is inactive');
            }
        })
        .catch(error => {
            console.error('Error loading rack info:', error);
            showError('Failed to load rack information');
        });
}

// Render rack information card
function renderRackInfo(rack) {
    document.getElementById('rack-code').textContent = rack.rack_code;
    document.getElementById('rack-name').textContent = rack.rack_name;
    document.getElementById('rack-type').innerHTML = getRackTypeBadge(rack.rack_type);

    if (rack.location_zone) {
        document.getElementById('rack-zone').innerHTML = `<span class="badge bg-info">${rack.location_zone}</span>`;
    } else {
        document.getElementById('rack-zone').style.display = 'none';
    }

    // Status badge with color based on status
    const statusBadge = document.getElementById('rack-status-badge');
    statusBadge.className = `badge ${getStatusClass(rack.status)}`;
    statusBadge.textContent = rack.status.toUpperCase();

    // Slot statistics
    const filledSlots = rack.filled_slots || 0;
    const availableSlots = rack.total_slots - filledSlots;

    document.getElementById('rack-total-slots').textContent = rack.total_slots;
    document.getElementById('rack-filled-slots').textContent = `${filledSlots} / ${rack.total_slots}`;
    document.getElementById('rack-available-slots').textContent = availableSlots;

    // Update action buttons visibility based on availability
    const actionButtons = document.getElementById('action-buttons');
    if (availableSlots > 0) {
        actionButtons.style.display = 'flex';
    } else {
        actionButtons.style.display = 'none';
    }
}

// Get rack type badge HTML
function getRackTypeBadge(rackType) {
    const badges = {
        'STORAGE_RACK': '<i class="fas fa-boxes me-1"></i>Storage',
        'QUICK_CHANGE_RACK': '<i class="fas fa-bolt me-1"></i>Quick Change',
        'INPRESS_RACK': '<i class="fas fa-industry me-1"></i>In-Press'
    };
    return badges[rackType] || `<i class="fas fa-box me-1"></i>${rackType}`;
}

// Get status CSS class
function getStatusClass(status) {
    const classes = {
        'AVAILABLE': 'bg-success',
        'IN_USE': 'bg-primary',
        'MAINTENANCE': 'bg-secondary'
    };
    return classes[status] || 'bg-dark';
}

// Load rack slot visualization
function loadRackSlots(rackId) {
    fetch(`/warehouse/api/racks/${rackId}/slots`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.slots) {
                renderSlotGrid(data.slots, rackId);
            } else {
                document.getElementById('slots-container').innerHTML = `
                    <div class="alert alert-danger">Failed to load slot information</div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading slots:', error);
            showError('Failed to load slot data');
        });
}

// Render slot grid visualization
function renderSlotGrid(slots, rackId) {
    const container = document.getElementById('slots-container');

    // Group slots into rows of 10 for better layout
    let html = '<div class="row g-2">';
    let rowStartIndex = 0;

    while (rowStartIndex < slots.length) {
        html += '<div class="col-md-6 col-lg-4"><div class="row g-1">';

        const maxPerRow = Math.ceil(slots.length - rowStartIndex);
        for (let i = 0; i < maxPerRow && i < 5; i++) { // Max 5 slots per column
            const slotIndex = rowStartIndex + i;
            if (slotIndex < slots.length) {
                const slot = slots[slotIndex];
                html += `<div class="col-12 mb-1">${renderSlotCard(slot, rackId)}</div>`;
            }
        }

        html += '</div></div>';
        rowStartIndex += 5; // Move to next row (5 columns)
    }

    html += '</div>';
    container.innerHTML = html;
}

// Render individual slot card
function renderSlotCard(slot, rackId) {
    if (slot.status === 'occupied') {
        return `
            <button onclick="openDieDetailModal(${slot.slot_number}, ${JSON.stringify(slot).replace(/"/g, '&quot;')})"
                    class="btn btn-light text-start w-100 h-100 position-relative border-success">
                <div class="d-flex align-items-center p-2">
                    <i class="fas fa-cog text-primary me-2"></i>
                    <div>
                        <strong>${slot.die_code}</strong><br>
                        ${slot.profile_code ? `<small class="text-muted">${slot.profile_code}</small>` : ''}
                        ${slot.alloy ? `<span class="badge bg-secondary ms-1">${slot.alloy}</span>` : ''}
                    </div>
                </div>
            </button>
        `;
    } else {
        return `
            <button onclick="openAssignDieModal(${slot.slot_number})"
                    class="btn btn-outline-success w-100 h-100 position-relative">
                <i class="fas fa-plus-circle me-2"></i>Slot ${slot.slot_number}
            </button>
        `;
    }
}

// Refresh rack data on demand
function loadRackInfo(rackId) {
    fetch(`/warehouse/api/racks/${rackId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.rack) {
                renderRackInfo(data.rack);
            } else {
                showError('Failed to load rack information');
            }
        })
        .catch(error => console.error('Error:', error));

    // Also refresh slots
    fetch(`/warehouse/api/racks/${rackId}/slots`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.slots) {
                renderSlotGrid(data.slots, rackId);
            }
        })
        .catch(error => console.error('Error loading slots:', error));
}

// Show error message in a toast notification
function showError(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger fixed-top';
    alert.style.cssText = 'padding: 1rem; margin: 1rem; z-index: 9999; min-width: 300px;';
    alert.innerHTML = `<i class="fas fa-exclamation-circle me-2"></i>${message}`;

    document.body.appendChild(alert);

    setTimeout(() => {
        alert.remove();
    }, 5000);
}

// Auto-focus barcode scanner input on page load
document.addEventListener('DOMContentLoaded', function() {
    // If we're in assign mode, focus the die code input
    const modal = bootstrap.Modal.getInstance(document.getElementById('assignDieModal'));
    if (modal && modal._isShown) {
        setTimeout(() => document.getElementById('assign-die-code').focus(), 300);
    }
});

// Handle barcode scanner auto-submit for assign die form
document.addEventListener('keypress', function(e) {
    const modal = bootstrap.Modal.getInstance(document.getElementById('assignDieModal'));
    if (!modal || !modal._isShown) return;

    // Store slot data when opening detail modal (global variable for remove operation)
    window.currentSlotData = null;

    if (e.key === 'Enter' && e.target.id === 'assign-die-code') {
        e.preventDefault();
        document.getElementById('assign-die-form').dispatchEvent(new Event('submit'));
    }
});
