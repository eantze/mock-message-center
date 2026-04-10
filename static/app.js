// Mock Message Center - Phase 1
// Minimal JS for interactivity

document.addEventListener('DOMContentLoaded', function () {
    // Highlight selected message in list on hover
    var items = document.querySelectorAll('.message-item');
    items.forEach(function (item) {
        item.addEventListener('mouseenter', function () {
            item.classList.add('hover');
        });
        item.addEventListener('mouseleave', function () {
            item.classList.remove('hover');
        });
    });

    // Stub action buttons
    document.querySelectorAll('.btn-secondary, .table-action').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            // No-op for Phase 1
        });
    });
});
