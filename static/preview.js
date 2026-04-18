const state = window.SOLVECHAIN_PREVIEW;

const feedbackForm = document.getElementById('feedback-form');
const feedbackInput = document.getElementById('feedback');
const statusEl = document.getElementById('status');
const errorEl = document.getElementById('error');
const logoutBtn = document.getElementById('logout-btn');
const menuToggle = document.getElementById('menu-toggle');
const navMenu = document.getElementById('nav-menu');

function showError(message) {
  errorEl.hidden = false;
  errorEl.textContent = message;
}

function clearError() {
  errorEl.hidden = true;
  errorEl.textContent = '';
}

async function postJSON(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || 'Request failed');
  }
  return payload;
}

function wireMenu() {
  if (!menuToggle || !navMenu) return;

  menuToggle.addEventListener('click', () => {
    const open = navMenu.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', String(open));
  });

  navMenu.querySelectorAll('a,button').forEach((item) => {
    item.addEventListener('click', () => {
      navMenu.classList.remove('open');
      menuToggle.setAttribute('aria-expanded', 'false');
    });
  });

  document.addEventListener('click', (event) => {
    if (!navMenu.classList.contains('open')) return;
    if (navMenu.contains(event.target) || menuToggle.contains(event.target)) return;
    navMenu.classList.remove('open');
    menuToggle.setAttribute('aria-expanded', 'false');
  });
}

feedbackForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  const feedback = feedbackInput.value.trim();
  if (feedback.length < 3) {
    showError('Please provide specific feedback (at least 3 characters).');
    return;
  }

  statusEl.textContent = 'Generating next version...';

  try {
    const payload = await postJSON('/api/feedback', {
      session_id: state.sessionId,
      feedback,
    });

    statusEl.textContent = 'Done. Opening the new version...';
    window.location.href = payload.preview_url;
  } catch (error) {
    statusEl.textContent = '';
    showError(error.message);
  }
});

logoutBtn.addEventListener('click', async () => {
  clearError();
  try {
    await postJSON('/api/auth/logout', {});
    window.location.href = '/#auth';
  } catch (error) {
    showError(error.message);
  }
});

wireMenu();
