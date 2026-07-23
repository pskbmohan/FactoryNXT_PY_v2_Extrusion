/**
 * Warehouse Transaction History JavaScript
 * Handles transaction filtering and CSV export functionality
 */

// Load transaction statistics on page load
document.addEventListener('DOMContentLoaded', function() {
    loadTransactionStats();
});

// Load transaction statistics
function loadTransactionStats() {
    fetch('/warehouse/api/transactions/stats')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const stats = data.statistics;
                let html = '<strong>Statistics:</strong><br>';

                stats.forEach(stat => {
                    html += `<span class="badge bg-${getBadgeColor(stat.type)} me-1 mb-1">${stat.count} ${stat.type}</span> `;
                });

                document.getElementById('transaction-stats').innerHTML = html || 'No transactions yet';

                // Update count badge if exists
                const countBadge = document.getElementById('transaction-count');
                if (countBadge) {
                    countBadge.textContent = `${stats.reduce((sum, s) => sum + s.count, 0)} records`;
                }
            }
        })
        .catch(error => console.error('Error loading stats:', error));

    // Update transaction count from template data
    const countBadge = document.getElementById('transaction-count');
    if (countBadge && typeof transactionsData !== 'undefined') {
        countBadge.textContent = `${transactionsData.length || 0} records`;
    }
}

// Get badge color for transaction type
function getBadgeColor(type) {
    switch(type.toUpperCase()) {
        case 'IN': return 'success';
        case 'OUT': return 'danger';
        case 'TRANSFER': return 'warning text-dark';
        default: return 'secondary';
    }
}

// View transaction detail (placeholder - implement as needed)
function viewTransactionDetail(transactionId) {
    alert('Transaction detail view coming soon. Transaction ID: ' + transactionId);
    // TODO: Implement modal with full transaction details
}

// Export transactions to CSV
function exportTransactions() {
    const form = document.getElementById('filter-form');
    const formData = new FormData(form);

    // Build CSV content from template data or API
    let csvContent = 'Type,Die Code,Profile,Alloy,Rack ID,Slot Number,Operator,Transaction Time,Notes\n';

    if (typeof transactionsData !== 'undefined' && transactionsData.length > 0) {
        transactionsData.forEach(tx => {
            const row = [
                tx.transaction_type || '',
                tx.die_code || '',
                tx.profile_code || '',
                tx.alloy || '',
                tx.rack_id || '',
                tx.slot_number || '',
                (tx.operator_id || '').replace(/,/g, ';'), // Escape commas
                formatDate(tx.transaction_time),
                (tx.notes || '').replace(/,/g, ';') // Escape commas in notes
            ];
            csvContent += row.join(',') + '\n';
        });

        downloadCSV(csvContent);
    } else {
        // If no data available from template, show message
        alert('No transactions to export. Try adjusting your filters.');
    }
}

// Download CSV file
function downloadCSV(content) {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `warehouse_transactions_${getDateString()}.csv`);
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showNotification('success', 'Transactions exported successfully!');
}

// Format date for CSV (handle both string and datetime objects)
function formatDate(dateValue) {
    if (!dateValue) return '';

    // If it's a string from template, parse it
    if (typeof dateValue === 'string') {
        const date = new Date(dateValue);
        if (!isNaN(date.getTime())) {
            return date.toISOString();
        }
        return dateValue;
    }

    // If it's a datetime object
    if (dateValue instanceof Date) {
        return dateValue.toISOString();
    }

    return String(dateValue);
}

// Get current date string for filename
function getDateString() {
    const now = new Date();
    return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
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

// Handle date input changes for better UX
document.querySelectorAll('input[type="date"]').forEach(input => {
    input.addEventListener('change', function() {
        // Auto-apply filter when dates change
        const form = this.closest('form');
        if (form) {
            setTimeout(() => form.submit(), 200);
        }
    });
});
