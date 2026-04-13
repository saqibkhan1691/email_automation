document.addEventListener('DOMContentLoaded', () => {
  const activateBtn = document.getElementById('activate-btn');
  const statusEl = document.getElementById('status');
  const emailsList = document.getElementById('emails-list');

  if (activateBtn) {
    activateBtn.addEventListener('click', async () => {
      activateBtn.disabled = true;
      statusEl.textContent = 'Processing…';
      statusEl.className = 'status processing';

      try {
        const res = await fetch('/api/run-workflow', { method: 'POST' });
        const data = await res.json();

        if (data.success) {
          statusEl.textContent = 'Done. Steps: ' + (data.steps || []).join(', ') || 'Completed.';
          statusEl.className = 'status success';
        } else {
          statusEl.textContent = 'Error: ' + (data.error || 'Unknown error');
          statusEl.className = 'status error';
        }
      } catch (err) {
        statusEl.textContent = 'Error: ' + err.message;
        statusEl.className = 'status error';
      } finally {
        activateBtn.disabled = false;
      }
    });
  }

  if (emailsList) {
    fetch('/api/emails')
      .then(res => res.json())
      .then(data => {
        if (data.emails && data.emails.length > 0) {
          emailsList.innerHTML = data.emails.map(e => `
            <div class="email-item">
              <div class="email-subject">${escapeHtml(e.subject || 'No subject')}</div>
              <div class="email-sender">${escapeHtml(e.sender || '')}</div>
            </div>
          `).join('');
        } else {
          emailsList.innerHTML = '<p class="muted">No recent unanswered emails.</p>';
        }
      })
      .catch(() => {
        emailsList.innerHTML = '<p class="muted">Could not load emails.</p>';
      });
  }
});

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
