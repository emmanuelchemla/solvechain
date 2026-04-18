const state = window.SOLVECHAIN_PREVIEW;

const logoutBtn = document.getElementById('logout-btn');
const menuToggle = document.getElementById('menu-toggle');
const navMenu = document.getElementById('nav-menu');

const ideaStrip = document.getElementById('idea-strip');
const selectedTitle = document.getElementById('selected-title');
const selectedFunction = document.getElementById('selected-function');
const selectedRationale = document.getElementById('selected-rationale');
const appFrame = document.getElementById('app-frame');

function normalizeErrorDetail(detail) {
  if (!detail) return 'Request failed';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
          const msg = item.msg || JSON.stringify(item);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      })
      .join('; ');
  }
  if (typeof detail === 'object') {
    if (detail.msg) return detail.msg;
    return JSON.stringify(detail);
  }
  return String(detail);
}

async function postJSON(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(normalizeErrorDetail(payload.detail));
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

function setActiveIdea(card) {
  ideaStrip.querySelectorAll('.idea-card').forEach((node) => node.classList.remove('active'));
  card.classList.add('active');
  selectedTitle.textContent = card.dataset.title;
  selectedFunction.innerHTML = `<strong>Function:</strong> ${card.dataset.function || ''}`;
  selectedRationale.innerHTML = `<strong>Rationale:</strong> ${card.dataset.rationale || ''}`;
  appFrame.src = card.dataset.appUrl;
}

function wireIdeaCards() {
  ideaStrip.querySelectorAll('.idea-card').forEach((card) => {
    card.addEventListener('click', () => setActiveIdea(card));
  });
}

function wireFeedbackBox(prefix) {
  const feedbackForm = document.getElementById(`${prefix}-feedback-form`);
  const feedbackInput = document.getElementById(`${prefix}-feedback-input`);
  const errorEl = document.getElementById(`${prefix}-error`);
  const feedbackThread = document.getElementById(`${prefix}-feedback-thread`);

  const openingMessage = prefix === 'ideas'
    ? 'What do you think about these ideas?'
    : 'What do you think about this app?';

  function showError(message) {
    errorEl.hidden = false;
    errorEl.textContent = message;
  }

  function clearError() {
    errorEl.hidden = true;
    errorEl.textContent = '';
  }

  function addBubble(role, text) {
    const item = document.createElement('article');
    item.className = `msg ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;

    item.appendChild(bubble);
    feedbackThread.appendChild(item);
    feedbackThread.scrollTop = feedbackThread.scrollHeight;
  }

  feedbackForm.addEventListener('submit', (event) => {
    event.preventDefault();
    clearError();

    const text = feedbackInput.value.trim();
    if (!text) return;

    addBubble('user', text);
    feedbackInput.value = '';
    addBubble('agent', 'What else');
  });

  feedbackInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && event.metaKey) {
      event.preventDefault();
      feedbackForm.requestSubmit();
    }
  });

  addBubble('agent', openingMessage);
}

logoutBtn.addEventListener('click', async () => {
  try {
    await postJSON('/api/auth/logout', {});
    window.location.href = '/#auth';
  } catch (error) {
    console.error(error);
  }
});

wireMenu();
wireIdeaCards();
wireFeedbackBox('ideas');
wireFeedbackBox('preview');
