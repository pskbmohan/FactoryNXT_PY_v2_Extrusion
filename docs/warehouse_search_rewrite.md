# Warehouse Search Module Rewrite

## Overview

This document describes the complete rewrite of the warehouse search module, including modernization of the backend `SearchService`, enhanced API endpoints, and improved frontend JavaScript interface.

## Changes Summary

### 1. Backend - Enhanced SearchService (`app/services/warehouse_service.py`)

#### New Features:
- **Pagination Support**: Results are now paginated with configurable page size (10-200 results per page)
- **Sorting Options**: Sort by `die_code`, `slot_number`, or `last_updated_at` in ascending/descending order
- **Fuzzy Search**: Added Levenshtein edit distance calculation for typo-tolerant search
- **Search Facets**: Endpoint to get aggregated counts for filter dropdowns (alloys, profiles, rack types, zones)
- **Improved Error Handling**: Better validation and error messages

#### New Methods:
| Method | Description |
|--------|-------------|
| `search_dies()` | Main search with pagination, sorting, and multiple filters |
| `search_dies_fuzzy()` | Fuzzy matching for typo tolerance (configurable threshold) |
| `get_search_facets()` | Returns aggregated counts for filter dropdowns |
| `_resolve_rack()` | Helper to resolve rack ID or code to database record |
| `_build_racks_map()` | Efficiently groups locations by parent rack |
| `_edit_distance()` | Levenshtein distance calculation for fuzzy matching |

### 2. API Endpoints (`app/routes/warehouse_management.py`)

#### Enhanced Search Endpoint:
```
GET /warehouse/api/search/dies
Query Parameters:
    - q: Search term (die_code or profile_code partial match)
    - profile: Exact profile code filter
    - alloy: Exact alloy type filter
    - rack: Rack UUID or code filter
    - page: Page number (default: 1, max per page: 200)
    - per_page: Results per page (default: 50, range: 10-200)
    - sort_by: Sort field ('die_code', 'slot_number', 'last_updated_at')
    - sort_order: Sort direction ('asc' or 'desc')

Response includes: total_results, total_pages, current_page, search_stats, results_by_rack
```

#### New Fuzzy Search Endpoint:
```
GET /warehouse/api/search/dies/fuzzy
Query Parameters:
    - q: Search term (minimum 3 characters)
    - threshold: Maximum edit distance allowed (default: 2, range: 1-5)

Returns suggestions sorted by match quality for autocomplete and typo correction.
```

#### New Facets Endpoint:
```
GET /warehouse/api/search/facets
Returns aggregated counts of all searchable values in the warehouse index.
Useful for building dynamic filter UIs without loading full result sets.
```

#### New Autocomplete Endpoint:
```
GET /warehouse/api/search/dies/autocomplete
Query Parameters:
    - q: Partial die code or profile (minimum 2 characters)
    - limit: Maximum suggestions (default: 10, max: 50)
    - include_profile: Include matching profiles in results

Returns quick suggestions for search input completion.
```

### 3. Frontend JavaScript (`templates/static/js/warehouse-search.js`)

#### New Features:
- **Debounced Search**: Input events are debounced (300ms delay) to reduce API calls
- **Keyboard Shortcuts**:
  - `Ctrl+F` / `Cmd+F`: Focus search input
  - `Enter`: Submit form or select autocomplete item
  - `Escape`: Clear current search and close autocomplete dropdown
  - Arrow keys: Navigate autocomplete suggestions

- **Autocomplete Suggestions**: Real-time suggestions as user types (minimum 2 characters)
- **Loading States**: Visual feedback during search operations with spinner animation
- **Search Statistics Display**: Shows active filters and result counts
- **Barcode Scanner Support**: Optimized for barcode scanner input patterns
- **Single Page Updates**: AJAX-based content updates without full page reloads

#### Code Structure:
```javascript
(function() {
    'use strict';

    const CONFIG = {
        DEBOUNCE_DELAY: 300,          // ms delay for debounced search
        AUTOFOCUS_TIMEOUT: 150,       // timeout before auto-focusing input
        MIN_SEARCH_LENGTH: 2,         // minimum chars for autocomplete
        MAX_AUTOCOMPLETE_RESULTS: 10, // max suggestions shown
    };

    const state = {
        currentSearch: null,
        debounceTimer: null,
        isSearching: false,
        pagination: { page: 1, perPage: 50, totalPages: 1 }
    };

    // Public API for external use
    window.WarehouseSearch = {
        focus: () => {...},
        performSearch: (term) => {...},
        clearSearch: () => {...}
    };
})();
```

### 4. HTML Template (`templates/warehouse/search.html`)

#### Improvements:
- Added keyboard shortcuts help banner at top of search form
- Autocomplete dropdown positioned below search input
- Better result display with grouped cards per rack
- Improved responsive layout for filter sections
- Dynamic visibility of filters based on available data
- Enhanced visual feedback (badges, icons)

## Technical Details

### Levenshtein Edit Distance Algorithm

The fuzzy search uses a dynamic programming approach to calculate edit distance:

```python
def _edit_distance(s1, s2):
    """Calculate minimum number of edits between two strings."""
    # Implementation using space-optimized DP algorithm
    # Time complexity: O(m*n), Space complexity: O(n)
```

### Search Performance Optimizations

1. **Index Usage**: Database indexes on `die_code`, `profile_code`, and `alloy` columns
2. **Pagination**: Limits query results to prevent large result sets from impacting performance
3. **Facet Caching**: Facet counts are computed once and reused for filter dropdowns
4. **Debouncing**: Reduces unnecessary API calls during rapid typing

### Database Schema Support

The search functionality relies on these indexes:

```python
# DieLocationIndex model indexes
__table_args__ = (
    db.UniqueConstraint('die_code', name='uq_die_code_current_location'),
    db.Index('ix_die_location_index_profile_code', 'profile_code'),
    db.Index('ix_die_location_index_alloy', 'alloy'),
    db.Index('ix_die_location_index_status', 'status')
)
```

## Usage Examples

### Basic Search via API:
```bash
curl "http://localhost:5000/warehouse/api/search/dies?q=ABC123"
```

### Fuzzy Search with Typo Tolerance:
```bash
# Find close matches to 'AB123' allowing up to 2 character differences
curl "http://localhost:5000/warehouse/api/search/dies/fuzzy?q=AB123&threshold=2"
```

### Get Filter Facets for UI Dropdowns:
```bash
curl "http://localhost:5000/warehouse/api/search/facets"
```

### Autocomplete Suggestions:
```bash
# Get suggestions as user types in search box
curl "http://localhost:5000/warehouse/api/search/dies/autocomplete?q=ABC&limit=10"
```

## Migration Notes

- Existing API calls to `/warehouse/api/search/dies` will continue to work (backward compatible)
- New pagination parameters are optional with sensible defaults
- The UI now uses AJAX for faster search without full page reloads
- All existing templates and routes remain functional

## Testing Recommendations

1. Test basic text search functionality
2. Verify fuzzy matching with intentional typos
3. Confirm pagination works correctly at boundaries
4. Check keyboard shortcuts on various browsers
5. Validate autocomplete suggestions appear/disappear appropriately
6. Test barcode scanner input patterns (rapid Enter key sequences)
7. Verify all filters work independently and in combination

## Future Enhancements

Potential improvements for future iterations:

1. **Redis Caching**: Cache frequently searched terms and results
2. **Elasticsearch Integration**: For more advanced full-text search capabilities
3. **Search Analytics**: Track popular searches to improve user experience
4. **Saved Searches**: Allow users to save common search queries
5. **Export Results**: Add ability to export search results to CSV/Excel

---

**Author**: Warehouse Management System Team  
**Date**: 2026-07-23  
**Version**: 2.0 (Rewrite)
