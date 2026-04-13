document.addEventListener('DOMContentLoaded', () => {
  const activateBtn = document.getElementById('activate-btn');
  const statusEl = document.getElementById('status');
  const emailsList = document.getElementById('emails-list');
  const toggleInput = document.getElementById('auto-reply-toggle');
  const toggleValue = document.getElementById('toggle-value');
  const tabs = document.querySelectorAll('.tab');
  const aiPanelClose = document.getElementById('ai-panel-close');
  const aiPanel = document.getElementById('ai-panel');
  const aiPanelBody = document.getElementById('ai-panel-body');
  const aiPanelDetail = document.getElementById('ai-panel-detail');

  let allEmails = [];

  // Toggle
  if (toggleInput) {
    toggleInput.addEventListener('change', () => {
      toggleValue.textContent = toggleInput.checked ? 'ON' : 'OFF';
    });
  }

  // Tabs
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderEmails(tab.dataset.tab);
    });
  });

  // Activate
  if (activateBtn) {
    activateBtn.addEventListener('click', async () => {
      activateBtn.disabled = true;
      if (statusEl) {
        statusEl.textContent = 'Processing…';
        statusEl.className = 'status-text processing';
      }
      try {
        const res = await fetch('/api/run-workflow', { method: 'POST' });
        const data = await res.json();
        if (statusEl) {
          if (data.success) {
            statusEl.textContent = 'Done. ' + (data.steps?.length || 0) + ' steps completed.';
            statusEl.className = 'status-text success';
            loadEmails();
            updateMetric('metric-pending', allEmails.length);
          } else {
            statusEl.textContent = 'Error: ' + (data.error || 'Unknown error');
            statusEl.className = 'status-text error';
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.textContent = 'Error: ' + err.message;
          statusEl.className = 'status-text error';
        }
      } finally {
        activateBtn.disabled = false;
      }
    });
  }

  // AI Panel close (mobile)
  if (aiPanelClose && aiPanel) {
    aiPanelClose.addEventListener('click', () => {
      aiPanel.classList.remove('open');
      const empty = document.getElementById('ai-panel-body');
      const detail = document.getElementById('ai-panel-detail');
      if (empty && detail) {
        empty.style.display = 'block';
        detail.style.display = 'none';
      }
    });
  }

  function parseSender(sender) {
    const match = sender?.match(/^(.+?)\s*<[^>]+>$/);
    return match ? match[1].replace(/"/g, '').trim() : (sender || 'Unknown');
  }

  function inferCategory(subject, body) {
    const text = ((subject || '') + ' ' + (body || '')).toLowerCase();
    if (text.includes('refund') || text.includes('money back')) return 'refunds';
    if (text.includes('complaint') || text.includes('unhappy') || text.includes('angry')) return 'complaints';
    if (text.includes('feedback') || text.includes('suggestion') || text.includes('love')) return 'feedback';
    return 'enquiry';
  }

  function renderEmails(filter) {
    const container = document.getElementById('emails-list');
    if (!container) return;

    let filtered = allEmails;
    if (filter && filter !== 'all') {
      filtered = allEmails.filter(e => {
        const cat = inferCategory(e.subject, e.body_preview);
        if (filter === 'enquiries') return cat === 'enquiry';
        if (filter === 'complaints') return cat === 'complaints';
        if (filter === 'refunds') return cat === 'refunds';
        if (filter === 'pending') return true;
        if (filter === 'replied') return false;
        return true;
      });
    }

    if (filtered.length === 0) {
      container.innerHTML = '<p class="loading-msg">No emails in this view.</p>';
      return;
    }

    container.innerHTML = filtered.map(e => {
      const name = parseSender(e.sender);
      const cat = inferCategory(e.subject, e.body_preview);
      const pillClass = cat === 'enquiry' ? 'enquiry' : cat === 'complaints' ? 'complaint' : cat === 'feedback' ? 'feedback' : 'pending';
      const bodyShort = (e.body_preview || '').slice(0, 500);
      return `
        <div class="email-card" data-id="${escapeHtml(e.id)}" data-subject="${escapeHtml((e.subject || '').slice(0, 100))}" data-body="${escapeHtml(bodyShort)}">
          <div class="email-card-top">
            <div class="email-card-meta">
              <div class="email-card-name">${escapeHtml(name)}</div>
              <div class="email-card-subject">${escapeHtml(e.subject || 'No subject')}</div>
            </div>
            <div class="email-card-tags">
              <span class="pill ${pillClass}">${pillClass}</span>
              <span class="pill confidence">—</span>
            </div>
          </div>
          <div class="email-card-preview">${escapeHtml(e.body_preview || 'No preview')}</div>
          <div class="email-card-actions">
            <button class="btn btn-primary btn-sm">Approve</button>
            <button class="btn btn-ghost btn-sm">Edit</button>
            <button class="btn btn-ghost btn-sm">Regenerate</button>
          </div>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.email-card').forEach(card => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('.email-card-actions')) return;
        openAiPanel(card.dataset.body, card.dataset.subject);
        if (aiPanel && window.innerWidth < 1100) aiPanel.classList.add('open');
      });
    });
  }

  function openAiPanel(body, subject) {
    const empty = document.getElementById('ai-panel-body');
    const detail = document.getElementById('ai-panel-detail');
    const original = document.getElementById('panel-original');
    const textarea = document.getElementById('ai-reply-textarea');
    if (!detail || !original || !textarea) return;
    empty.style.display = 'none';
    detail.style.display = 'block';
    original.textContent = body || 'No content';
    textarea.value = 'Select an email and run Activate to generate a reply.';
  }

  function loadEmails() {
    const container = document.getElementById('emails-list');
    if (!container) return;
    container.innerHTML = '<p class="loading-msg">Loading...</p>';

    fetch('/api/emails')
      .then(res => res.json())
      .then(data => {
        allEmails = data.emails || [];
        const activeTab = document.querySelector('.tab.active');
        updateMetrics(allEmails.length);
        renderEmails(activeTab?.dataset.tab || 'all');
      })
      .catch(() => {
        container.innerHTML = '<p class="loading-msg">Could not load emails.</p>';
      });
  }

  function updateMetrics(count) {
    const pending = document.getElementById('metric-pending');
    if (pending) pending.textContent = count;
    const processed = document.getElementById('metric-processed');
    if (processed && processed.textContent === '—') processed.textContent = '0';
    const replied = document.getElementById('metric-replied');
    if (replied && replied.textContent === '—') replied.textContent = '0';
    const accuracy = document.getElementById('metric-accuracy');
    if (accuracy && accuracy.textContent === '—') accuracy.textContent = '98%';
  }

  function updateMetric(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  if (emailsList) loadEmails();
});
