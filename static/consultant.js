const state = {
  sessionId: null,
  versions: [],
};

const startForm = document.getElementById('start-form');
const painPointInput = document.getElementById('pain-point');
const sessionNote = document.getElementById('session-note');

const discoveryPanel = document.getElementById('discovery-panel');
const questionEl = document.getElementById('question');
const answerForm = document.getElementById('answer-form');
const answerInput = document.getElementById('answer');
const remainingEl = document.getElementById('remaining');
const generateBtn = document.getElementById('generate-btn');

const outputPanel = document.getElementById('output-panel');
const versionsEl = document.getElementById('versions');
const feedbackForm = document.getElementById('feedback-form');
const feedbackInput = document.getElementById('feedback');

const logoutBtn = document.getElementById('logout-btn');
const errorEl = document.getElementById('error');

function showError(message) {
  errorEl.hidden = false;
  errorEl.textContent = message;
}

function clearError() {
  errorEl.hidden = true;
  errorEl.textContent = '';
}

function setQuestion(question, remaining) {
  questionEl.textContent = question;
  remainingEl.textContent = `Questions remaining: ${remaining}`;
}

function renderVersions() {
  if (!state.versions.length) {
    versionsEl.innerHTML = '<p class="muted">No versions generated yet.</p>';
    return;
  }

  versionsEl.innerHTML = state.versions
    .map((version) => {
      const features = version.features.map((item) => `<li>${item}</li>`).join('');
      return `
        <article class="version">
          <h3>Version ${version.version}</h3>
          <p>${version.summary}</p>
          <ul>${features}</ul>
          <a href="${version.download}" target="_blank" rel="noopener">Download FastAPI project ZIP</a>
        </article>
      `;
    })
    .join('');
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

startForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  const painPoint = painPointInput.value.trim();
  if (painPoint.length < 10) {
    showError('Please provide a more specific pain point (at least 10 characters).');
    return;
  }

  try {
    const payload = await postJSON('/api/session/start', { pain_point: painPoint });
    state.sessionId = payload.session_id;
    state.versions = [];

    sessionNote.textContent = `Session: ${payload.session_id}`;
    discoveryPanel.hidden = false;
    outputPanel.hidden = true;
    generateBtn.hidden = true;

    setQuestion(payload.question, payload.remaining);
    answerInput.value = '';
    renderVersions();
  } catch (error) {
    if (error.message === 'Authentication required') {
      window.location.href = '/#auth';
      return;
    }
    showError(error.message);
  }
});

answerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  if (!state.sessionId) {
    showError('Start a session first.');
    return;
  }

  const answer = answerInput.value.trim();
  if (!answer) {
    showError('Please answer the question before submitting.');
    return;
  }

  try {
    const payload = await postJSON('/api/session/answer', {
      session_id: state.sessionId,
      answer,
    });

    answerInput.value = '';

    if (payload.done) {
      questionEl.textContent = payload.message;
      remainingEl.textContent = 'Discovery completed.';
      generateBtn.hidden = false;
      return;
    }

    setQuestion(payload.question, payload.remaining);
  } catch (error) {
    showError(error.message);
  }
});

generateBtn.addEventListener('click', async () => {
  clearError();

  try {
    const version = await postJSON('/api/generate', {
      session_id: state.sessionId,
    });

    state.versions.unshift(version);
    outputPanel.hidden = false;
    renderVersions();
  } catch (error) {
    showError(error.message);
  }
});

feedbackForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  if (!state.sessionId) {
    showError('Start a session first.');
    return;
  }

  if (!state.versions.length) {
    showError('Generate the first version before using feedback.');
    return;
  }

  const feedback = feedbackInput.value.trim();
  if (feedback.length < 3) {
    showError('Feedback should be at least 3 characters.');
    return;
  }

  try {
    const version = await postJSON('/api/feedback', {
      session_id: state.sessionId,
      feedback,
    });

    feedbackInput.value = '';
    state.versions.unshift(version);
    renderVersions();
  } catch (error) {
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
