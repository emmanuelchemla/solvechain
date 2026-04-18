const authForm = document.getElementById('auth-form');
const authError = document.getElementById('auth-error');
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

function setAuthenticated(user) {
  // no-op on landing page; successful auth redirects to consultant
}

function setAnonymous() {
  // no-op on landing page
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

authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  const nameInput = document.getElementById('auth-name').value.trim();
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;

  try {
    const payload = await postJSON('/api/auth/login', { email, password });
    setAuthenticated(payload);
    window.location.href = '/consultant';
  } catch (error) {
    if (error.message !== 'Invalid credentials') {
      showError(error.message);
      return;
    }

    const fallbackName = nameInput || email.split('@')[0] || 'New User';
    try {
      const payload = await postJSON('/api/auth/register', {
        name: fallbackName,
        email,
        password,
      });
      setAuthenticated(payload);
      window.location.href = '/consultant';
    } catch (registerError) {
      showError(registerError.message);
    }
  }
});

wireMenu();
wireScrollReveal();
loadAuth().catch((error) => showError(error.message));
