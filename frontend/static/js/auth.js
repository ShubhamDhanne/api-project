/**
 * auth.js — Handles login and registration form submissions.
 */

document.addEventListener('DOMContentLoaded', () => {
  // If already logged in, skip straight to dashboard
  if (getToken() && (window.location.pathname === '/login' || window.location.pathname === '/register')) {
    window.location.href = '/dashboard';
    return;
  }

  // ── Login form ──────────────────────────────────────────────────────────
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    // Toggle password visibility
    document.getElementById('toggle-pwd')?.addEventListener('click', () => {
      const pwd = document.getElementById('password');
      const icon = document.querySelector('#toggle-pwd i');
      if (pwd.type === 'password') {
        pwd.type = 'text';
        icon.classList.replace('fa-eye', 'fa-eye-slash');
      } else {
        pwd.type = 'password';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
      }
    });

    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const errorEl = document.getElementById('login-error');
      const btn = document.getElementById('login-btn');
      const spinner = document.getElementById('login-spinner');

      errorEl.classList.add('d-none');
      btn.disabled = true;
      spinner.classList.remove('d-none');

      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        const data = await res.json();

        if (data.success) {
          saveAuth(data.data.token, { name: data.data.name, email: data.data.email });
          window.location.href = '/dashboard';
        } else {
          errorEl.textContent = data.error || 'Login failed.';
          errorEl.classList.remove('d-none');
        }
      } catch {
        errorEl.textContent = 'Network error. Please try again.';
        errorEl.classList.remove('d-none');
      } finally {
        btn.disabled = false;
        spinner.classList.add('d-none');
      }
    });
  }

  // ── Register form ────────────────────────────────────────────────────────
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    document.getElementById('toggle-pwd')?.addEventListener('click', () => {
      const pwd = document.getElementById('password');
      const icon = document.querySelector('#toggle-pwd i');
      if (pwd.type === 'password') {
        pwd.type = 'text';
        icon.classList.replace('fa-eye', 'fa-eye-slash');
      } else {
        pwd.type = 'password';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
      }
    });

    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('name').value.trim();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const confirm = document.getElementById('confirm-password').value;
      const errorEl = document.getElementById('register-error');
      const successEl = document.getElementById('register-success');
      const btn = document.getElementById('register-btn');
      const spinner = document.getElementById('register-spinner');

      errorEl.classList.add('d-none');
      successEl.classList.add('d-none');

      // Client-side validation
      if (password !== confirm) {
        errorEl.textContent = 'Passwords do not match.';
        errorEl.classList.remove('d-none');
        return;
      }
      if (password.length < 8) {
        errorEl.textContent = 'Password must be at least 8 characters.';
        errorEl.classList.remove('d-none');
        return;
      }

      btn.disabled = true;
      spinner.classList.remove('d-none');

      try {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, password }),
        });
        const data = await res.json();

        if (data.success) {
          successEl.textContent = 'Account created! Redirecting to login…';
          successEl.classList.remove('d-none');
          setTimeout(() => { window.location.href = '/login'; }, 1500);
        } else {
          errorEl.textContent = data.error || 'Registration failed.';
          errorEl.classList.remove('d-none');
        }
      } catch {
        errorEl.textContent = 'Network error. Please try again.';
        errorEl.classList.remove('d-none');
      } finally {
        btn.disabled = false;
        spinner.classList.add('d-none');
      }
    });
  }
});
