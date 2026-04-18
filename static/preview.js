const state = window.SOLVECHAIN_PREVIEW;

const logoutBtn = document.getElementById('logout-btn');
const menuToggle = document.getElementById('menu-toggle');
const navMenu = document.getElementById('nav-menu');

const ideaStrip = document.getElementById('idea-strip');
const generationStatus = document.getElementById('generation-status');
const generationFill = document.getElementById('generation-fill');

const previewEmpty = document.getElementById('preview-empty');
const selectedTitle = document.getElementById('selected-title');
const selectedFunction = document.getElementById('selected-function');
const selectedRationale = document.getElementById('selected-rationale');
const appFrame = document.getElementById('app-frame');

function setGenerationStatus(text) {
  if (generationStatus) generationStatus.textContent = text;
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

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function parseImportance(raw) {
  const match = String(raw || '').match(/\d+/);
  return match ? Number(match[0]) : 0;
}

function shuffle(items) {
  const array = [...items];
  for (let i = array.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
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

function clearPreview() {
  previewEmpty.hidden = false;
  selectedTitle.hidden = true;
  selectedFunction.hidden = true;
  selectedRationale.hidden = true;
  appFrame.hidden = true;
  appFrame.src = 'about:blank';
}

function setActiveIdea(card) {
  ideaStrip.querySelectorAll('.idea-card').forEach((node) => node.classList.remove('active'));
  card.classList.add('active');

  previewEmpty.hidden = true;
  selectedTitle.hidden = false;
  selectedFunction.hidden = false;
  selectedRationale.hidden = false;
  appFrame.hidden = false;

  selectedTitle.textContent = card.dataset.title;
  selectedFunction.innerHTML = `<strong>Function:</strong> ${card.dataset.function || ''}`;
  selectedRationale.innerHTML = `<strong>Rationale:</strong> ${card.dataset.rationale || ''}`;
  appFrame.src = card.dataset.appUrl;
}

function sortVisibleCardsAnimated(allCards) {
  const visibleCards = allCards.filter((card) => card.classList.contains('show'));
  if (visibleCards.length < 2) return;

  const firstRects = new Map();
  visibleCards.forEach((card) => {
    firstRects.set(card, card.getBoundingClientRect());
  });

  const ordered = [...visibleCards].sort(
    (a, b) => parseImportance(b.dataset.importance) - parseImportance(a.dataset.importance)
  );
  ordered.forEach((card) => ideaStrip.appendChild(card));

  ordered.forEach((card) => {
    const first = firstRects.get(card);
    const last = card.getBoundingClientRect();
    const deltaX = first.left - last.left;
    const deltaY = first.top - last.top;
    if (!deltaX && !deltaY) return;

    card.animate(
      [
        { transform: `translate(${deltaX}px, ${deltaY}px)` },
        { transform: 'translate(0, 0)' },
      ],
      {
        duration: 360,
        easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
      }
    );
  });
}

function animateGlobalProgress(durationMs) {
  return new Promise((resolve) => {
    if (!generationFill) {
      window.setTimeout(resolve, durationMs);
      return;
    }

    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      generationFill.style.width = '100%';
      resolve();
    };

    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const pct = Math.min(100, (elapsed / durationMs) * 100);
      generationFill.style.width = `${pct}%`;
      if (pct >= 100) {
        window.clearInterval(timer);
        finish();
      }
    }, 50);
    window.setTimeout(() => {
      window.clearInterval(timer);
      finish();
    }, durationMs + 1200);
  });
}

function runCardProgress(card) {
  const fill = card.querySelector('.card-progress-fill');
  const min = 1000;
  const max = 5000;
  const duration = min + Math.random() * (max - min);

  return new Promise((resolve) => {
    if (!fill) {
      card.dataset.ready = 'true';
      card.classList.add('ready');
      resolve();
      return;
    }

    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const pct = Math.min(100, (elapsed / duration) * 100);
      fill.style.width = `${pct}%`;
      if (pct >= 100) {
        window.clearInterval(timer);
        card.dataset.ready = 'true';
        card.classList.add('ready');
        resolve();
      }
    }, 50);
  });
}

function wireIdeaCards() {
  const cards = Array.from(ideaStrip.querySelectorAll('.idea-card'));

  cards.forEach((card) => {
    card.addEventListener('click', () => {
      if (card.dataset.ready !== 'true') return;
      setActiveIdea(card);
    });
  });

  return cards;
}

async function startIdeaGeneration(cards) {
  if (!ideaStrip) return;

  if (!cards.length) {
    setGenerationStatus('No ideas available yet.');
    if (generationFill) generationFill.style.width = '0%';
    return;
  }

  try {
    ideaStrip.classList.add('generating');
    cards.forEach((card) => {
      card.classList.remove('show', 'ready', 'active');
      card.dataset.ready = 'false';
      if (card.parentElement === ideaStrip) {
        ideaStrip.removeChild(card);
      }
    });

    setGenerationStatus('Synthesizing and ranking ideas...');
    await animateGlobalProgress(4000);
    setGenerationStatus('Ideas incoming. Scoring each concept...');

    const appearanceOrder = shuffle(cards);
    const completionTasks = [];

    for (const card of appearanceOrder) {
      ideaStrip.appendChild(card);
      card.classList.add('show');
      sortVisibleCardsAnimated(cards);
      completionTasks.push(runCardProgress(card));
      await sleep(280);
    }

    await Promise.all(completionTasks);
    setGenerationStatus('All ideas are ready. Select any idea to preview.');
    ideaStrip.classList.remove('generating');
  } catch (error) {
    console.error(error);
    setGenerationStatus('Ideas ready. Select one to preview.');
    ideaStrip.classList.remove('generating');
    cards.forEach((card) => {
      if (card.parentElement !== ideaStrip) {
        ideaStrip.appendChild(card);
      }
      card.classList.add('show', 'ready');
      card.dataset.ready = 'true';
      const fill = card.querySelector('.card-progress-fill');
      if (fill) fill.style.width = '100%';
    });
  }
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
    if (!text) {
      showError('Please add a short note before sending.');
      return;
    }

    addBubble('user', text);
    feedbackInput.value = '';
    addBubble('agent', 'What else');
  });

  feedbackInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      feedbackForm.requestSubmit();
    }
  });

  addBubble('agent', openingMessage);
}

if (logoutBtn) {
  logoutBtn.addEventListener('click', async () => {
    try {
      await postJSON('/api/auth/logout', {});
      window.location.href = '/#auth';
    } catch (error) {
      console.error(error);
    }
  });
}

wireMenu();
clearPreview();
if (ideaStrip) {
  const cards = wireIdeaCards();
  startIdeaGeneration(cards);
}
wireFeedbackBox('ideas');
wireFeedbackBox('preview');
