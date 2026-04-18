const openingPrompt = 'Let us see how I can help. I will ask a couple of questions about your daily job. Let us start right away: what could be automated in your daily job?';
const scriptedReplies = [
  'Ok, how important is that pain point for you?',
  'Ok, how important is that pain point for you?',
];
const fallbackReply = 'Excellent, thank you. Is there any other idea, pain point, difficulty you would like to tell me about';

const state = {
  replyIndex: 0,
  responses: [],
};

const chatThread = document.getElementById('chat-thread');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const doneBtn = document.getElementById('done-btn');
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

function addBubble(role, text) {
  const item = document.createElement('article');
  item.className = `msg ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;

  item.appendChild(bubble);
  chatThread.appendChild(item);
  chatThread.scrollTop = chatThread.scrollHeight;
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

chatForm.addEventListener('submit', (event) => {
  event.preventDefault();
  clearError();

  const text = chatInput.value.trim();
  if (!text) return;

  addBubble('user', text);
  state.responses.push(text);
  chatInput.value = '';

  const reply = state.replyIndex < scriptedReplies.length
    ? scriptedReplies[state.replyIndex++]
    : fallbackReply;
  addBubble('agent', reply);

  if (state.responses.length >= 1) {
    doneBtn.disabled = false;
    statusEl.textContent = '';
  }
});

chatInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && event.metaKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

doneBtn.addEventListener('click', async () => {
  clearError();

  if (!state.responses.length) {
    showError('Please answer at least one prompt first.');
    return;
  }

  doneBtn.disabled = true;
  statusEl.textContent = 'Generating your app...';

  try {
    const painPoint = state.responses[0];
    const start = await postJSON('/api/session/start', { pain_point: painPoint });
    const sessionId = start.session_id;

    const synthesis = [
      `Pain point: ${state.responses[0] || 'N/A'}`,
      `Importance: ${state.responses[1] || 'High'}`,
      `Additional context: ${state.responses[2] || 'N/A'}`,
    ].join('\n');

    let cursor = start;
    while (!cursor.done) {
      const answerPayload = await postJSON('/api/session/answer', {
        session_id: sessionId,
        answer: synthesis,
      });
      cursor = answerPayload;
      if (cursor.done) break;
    }

    const version = await postJSON('/api/generate', { session_id: sessionId });
    statusEl.textContent = 'Done. Opening live preview...';
    window.location.href = version.preview_url;
  } catch (error) {
    doneBtn.disabled = false;
    statusEl.textContent = '';
    if (error.message === 'Authentication required') {
      window.location.href = '/#auth';
      return;
    }
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

addBubble('agent', openingPrompt);
wireMenu();
