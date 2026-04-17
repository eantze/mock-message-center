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

// --- Phase 3: Glossary drawer ---

function toggleGlossary() {
    var drawer = document.getElementById('glossaryDrawer');
    if (!drawer) return;
    drawer.classList.toggle('open');
}

function loadDefinition(term, idx) {
    var btn = document.querySelector('#term-' + idx + ' .glossary-load-btn');
    var defEl = document.getElementById('def-' + idx);
    if (!btn || !defEl) return;
    btn.disabled = true;
    btn.textContent = 'Loading…';
    var form = new FormData();
    fetch('/api/glossary/' + encodeURIComponent(term), { method: 'POST', body: form })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.definition) {
                defEl.textContent = data.definition;
                defEl.classList.add('loaded');
                btn.style.display = 'none';
            } else {
                btn.textContent = 'Error — retry';
                btn.disabled = false;
            }
        })
        .catch(function() {
            btn.textContent = 'Error — retry';
            btn.disabled = false;
        });
}

// --- Phase 3: Ask-a-question modal ---

var askHistory = [];

function openAskModal() {
    var msgData = document.getElementById('msgData');
    if (!msgData) return;
    var subject = msgData.getAttribute('data-subject');
    document.getElementById('askModalSubject').textContent = 'Re: ' + subject;
    document.getElementById('askModal').style.display = 'flex';
    document.getElementById('askInput').focus();
}

function closeAskModal(evt) {
    if (evt && evt.target !== document.getElementById('askModal')) return;
    document.getElementById('askModal').style.display = 'none';
}

function addBubble(role, text) {
    var history = document.getElementById('askChatHistory');
    var bubble = document.createElement('div');
    bubble.className = 'chat-bubble ' + role;
    bubble.textContent = text;
    history.appendChild(bubble);
    history.scrollTop = history.scrollHeight;
    return bubble;
}

function sendAsk() {
    var input = document.getElementById('askInput');
    var sendBtn = document.getElementById('askSendBtn');
    var msgData = document.getElementById('msgData');
    var userMsg = input.value.trim();
    if (!userMsg || !msgData) return;
    var messageId = msgData.getAttribute('data-message-id');

    addBubble('user', userMsg);
    input.value = '';
    sendBtn.disabled = true;
    var thinking = addBubble('thinking', 'Thinking…');

    fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: parseInt(messageId), history: askHistory, user_msg: userMsg })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        thinking.remove();
        if (data.reply) {
            addBubble('model', data.reply);
            // Append turn to local history
            askHistory.push({ role: 'user', parts: [userMsg] });
            askHistory.push({ role: 'model', parts: [data.reply] });
        } else {
            addBubble('thinking', 'Sorry, something went wrong. ' + (data.error || ''));
        }
        sendBtn.disabled = false;
        document.getElementById('askInput').focus();
    })
    .catch(function() {
        thinking.remove();
        addBubble('thinking', 'Network error. Please try again.');
        sendBtn.disabled = false;
    });
}

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
