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

});

// --- Document Center: move attachment ---
function moveToDocCenter(btn) {
    var attachmentId = btn.getAttribute('data-attachment-id');
    var folder = prompt('Move to which folder? (leave blank for "Unfiled")', 'Unfiled');
    if (folder === null) return; // cancelled
    if (!folder.trim()) folder = 'Unfiled';
    var form = new FormData();
    form.append('attachment_id', attachmentId);
    form.append('folder', folder.trim());
    fetch('/api/documents/move', { method: 'POST', body: form })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.ok) {
                btn.textContent = 'Moved to ' + data.folder;
                btn.disabled = true;
                btn.classList.add('btn-moved');
            } else {
                alert(data.error || 'Error moving document');
            }
        });
}
