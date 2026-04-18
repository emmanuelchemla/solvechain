const registerForm = document.getElementById('register-form');
const loginForm = document.getElementById('login-form');
const logoutBtn = document.getElementById('logout-btn');
const authError = document.getElementById('auth-error');
const authState = document.getElementById('auth-state');
const consultantLink = document.getElementById('consultant-link');
const menuToggle = document.getElementById('menu-toggle');
const navMenu = document.getElementById('nav-menu');

function showError(message) {
  authError.hidden = false;
  authError.textContent = message;
}

function clearError() {
  authError.hidden = true;
  authError.textContent = '';
}

function setAuthenticated(user) {
  authState.textContent = `Signed in as ${user.name} (${user.email}).`;
  consultantLink.hidden = false;
  logoutBtn.hidden = false;
}

function setAnonymous() {
  authState.textContent = 'Create an account or login to access the consultant app.';
  consultantLink.hidden = true;
  logoutBtn.hidden = true;
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

async function loadAuth() {
  clearError();
  const response = await fetch('/api/auth/me');
  const payload = await response.json();
  if (payload.authenticated) {
    setAuthenticated(payload);
  } else {
    setAnonymous();
  }
}

function wireScrollReveal() {
  const elements = document.querySelectorAll('.reveal');
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.18 }
  );

  elements.forEach((element) => observer.observe(element));
}

function wireMenu() {
  if (!menuToggle || !navMenu) return;

  menuToggle.addEventListener('click', () => {
    const open = navMenu.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', String(open));
  });

  navMenu.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
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

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  const body = {
    name: document.getElementById('register-name').value.trim(),
    email: document.getElementById('register-email').value.trim(),
    password: document.getElementById('register-password').value,
  };

  try {
    const payload = await postJSON('/api/auth/register', body);
    setAuthenticated(payload);
    window.location.href = '/consultant';
  } catch (error) {
    showError(error.message);
  }
});

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  const body = {
    email: document.getElementById('login-email').value.trim(),
    password: document.getElementById('login-password').value,
  };

  try {
    const payload = await postJSON('/api/auth/login', body);
    setAuthenticated(payload);
    window.location.href = '/consultant';
  } catch (error) {
    showError(error.message);
  }
});

logoutBtn.addEventListener('click', async () => {
  clearError();
  try {
    await postJSON('/api/auth/logout', {});
    setAnonymous();
  } catch (error) {
    showError(error.message);
  }
});

wireMenu();
wireScrollReveal();
loadAuth().catch((error) => showError(error.message));
